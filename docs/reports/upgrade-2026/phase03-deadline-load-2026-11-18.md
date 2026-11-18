# Báo cáo Triển khai Đợt 3: Kiểm soát Thời gian Xử lý & Tải (R02, R03)

- **Ngày thực hiện:** 2026-11-18
- **Tham chiếu đánh giá:** `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md`, `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`, `docs/reports/upgrade-2026/phase02-evidence-provenance-2026-11-18.md`
- **Branch / HEAD baseline:** `main` @ `4e64f97` (đã bao gồm Đợt 1 `627be4e` và Đợt 2 `4e64f97`)
- **Thay đổi có sẵn được giữ nguyên:** `README.md` (chỉnh sửa chưa commit của người dùng), `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md`, `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`
- **Trạng thái bàn giao:** **Đợt 3 source-ready; HTTP fault-injection cô lập đã kiểm tra; chưa deploy hệ thống hiện hữu.**

---

## 1. Baseline và Tái hiện Lỗi Trước Sửa

Trước khi sửa source, toàn bộ 5 nhóm lỗi R02/R03 được tái hiện lại trên revision `4e64f97` trong process bằng mock cô lập (không gọi provider trả phí):

| Nhóm lỗi | Kịch bản tái hiện | Kết quả trước sửa | Nguyên nhân gốc |
|---|---|---|---|
| **R02a — OpenAI timeout & SDK retries** | Gọi `openai_chat_complete(..., timeout=0.05)` với `LLM_PROVIDER=openai` | `timeout` không có trong kwargs của `completions.create` (`create_keys=['max_tokens','messages','model','temperature']`); `OpenAI()` mặc định `max_retries=2` | `_chat_with_openai` không nhận/truyền `timeout`; `get_openai_client()` không tắt `max_retries` |
| **R02b — Custom provider timeout** | Gọi `openai_chat_complete(..., timeout=0.05)` với `LLM_PROVIDER=custom` | `requests.post` nhận `timeout=60` (`LLM_TIMEOUT` toàn cục) | `_chat_with_custom_api` dùng cố định `timeout=LLM_TIMEOUT` |
| **R02c — Fallback bỏ qua deadline ban đầu** | Primary Ollama đốt 0,12s trên budget 0,10s rồi lỗi; có `OPENAI_API_KEY` | Fallback sang OpenAI vẫn được gọi dù ngân sách đã cạn (`fallback_timeout_passed=None`) | `openai_chat_complete` không chia sẻ monotonic deadline giữa primary và fallback |
| **R02d — Lazy init / cache probe ngoài budget** | Khởi tạo `CustomEmbeddingService`, `QdrantClient`, `get_redis_client` | `CustomEmbeddingService.__init__` gọi `requests.get(/health, timeout=5)`; `QdrantClient` chạy compatibility probe ngoài budget; `get_redis_client` gọi DNS `getaddrinfo("valkey-db")` đồng bộ (~30s trên Windows không có Docker DNS) và ghi `_redis_last_attempt` trước khi probe | Không tách lazy init khỏi network probe; `socket_connect_timeout` không chặn được OS DNS hang |
| **R03a — Event loop bị chặn** | Thay `hybrid_search` bằng hàm đồng bộ ngủ 200 ms; đo timer `asyncio.sleep(0.01)` song song với `await search_endpoint(...)` | Timer 10 ms chỉ chạy sau **200,88 ms** | `/search`, `/summarize`, `/health`, indexing, `/chat/complete/{task_id}` khai báo `async def` nhưng gọi trực tiếp I/O đồng bộ |
| **R03b — Không giới hạn input / admission / auth** | Tạo `SummaryRequest(text="a"*500000)` và kiểm tra concurrency/auth | Chấp nhận 500.000 ký tự; không có giới hạn concurrency/queue/rate-limit riêng; `/search` và `/summarize` mở công khai cả ở `production` | Thiếu validation max length, thiếu execution lanes và rate limiter |

---

## 2. Kiến trúc Thống nhất Deadline End-to-End (R02)

Module trung tâm mới/nâng cấp: **`backend/src/harness/budget.py`** (`RequestBudget`, `BudgetExhaustedError`, `resolve_deadline`, `remaining_for_call`, `call_with_supported_kwargs`).

### 2.1 Điểm bắt đầu, trần server-side và truyền qua các tầng

- **Đồng hồ:** `time.monotonic()` duy nhất (chống lệch wall-clock).
- **Trần server-side:** client không có trường truyền timeout. Chat bị kẹp trần cứng `AGENT_MAX_REQUEST_TIMEOUT_SECONDS <= 55.0`s (mặc định `AGENT_REQUEST_TIMEOUT_SECONDS = 50.0`s, thấp hơn gate 60s). `/search` trần `30s` (mặc định `15s`), `/summarize` trần `45s` (mặc định `25s`), indexing trần `55s` (mặc định `45s`), health/readiness probe trần `10s` (mặc định `5s`).
- **Luồng truyền deadline:**
  1. **HTTP boundary (`api/app.py`):** tạo một `RequestBudget` duy nhất ngay sau auth/validation -> truyền vào kiểm tra rate limit (với sub-budget tối đa 2s), chờ admission trong `BoundedWorkLane`, và truyền `deadline_monotonic` + `cancel_event` xuống tầng nghiệp vụ.
  2. **Chat (`memory/chat.py` -> `agents/graph.py`):** nhận `deadline_monotonic` (hoặc tự khởi tạo budget hợp lệ nếu gọi trực tiếp ngoài HTTP). Thời gian nạp profile/DB/history được trừ vào cùng budget; nếu đã cạn trước khi chạy graph thì trả degraded fallback ngay (giữ nguyên `safety_result`).
  3. **Các node graph:**
     - `normalize_question_agent`: tính timeout còn lại trừ `AGENT_COMPOSER_RESERVE_SECONDS`, truyền xuống `detect_user_intent`; nếu không đủ thì giữ nguyên câu hỏi gốc, không gọi LLM.
     - `supervisor_agent`: tính timeout còn lại trừ reserve, truyền xuống `detect_route`; nếu không đủ thì dùng `_keyword_route` ngay, không gọi LLM.
     - `rag_agent`: dùng chung deadline cho `rewrite_query_to_multi_queries` -> `hybrid_search` (`get_embedding` -> `search_vector`) -> `rerank_documents`.
     - `web_search_agent`: tính timeout còn lại trừ `AGENT_COMPOSER_RESERVE_SECONDS`, truyền xuống `tavily_search_health`; nếu không đủ thì bỏ qua, không gọi Tavily.
     - `ZepMemory`: tính timeout trừ reserve, truyền `timeout_in_seconds` + `max_retries=0` vào `zep_memory.recall`.
     - `response_composer_agent`: tính timeout còn lại (trừ dự phòng kết thúc 0,15s), truyền `timeout` và `attempt_deadline` xuống `openai_chat_complete` / `vietnamese_llm_chat_complete`.
  4. **Các adapter thực thi:**
     - **Ollama (`llm/client.py`):** truyền `effective_timeout` vào `requests.post`.
     - **OpenAI (`llm/client.py`):** khởi tạo `OpenAI(..., max_retries=0, timeout=...)`, áp dụng `with_options(max_retries=0, timeout=...)` và truyền `timeout=effective_timeout` vào `client.chat.completions.create`.
     - **Custom/Vietnamese API (`llm/client.py`):** truyền `effective_timeout` vào `requests.post` (thay `LLM_TIMEOUT`).
     - **Embedding (`llm/embedding.py`):** bỏ health probe trong `__init__`; tính `effective_timeout` từ deadline và truyền vào `requests.post`.
     - **Qdrant (`rag/qdrant/client.py` + `rag/search.py`):** tắt `check_compatibility` probe khi SDK hỗ trợ; vì Qdrant API dùng số nguyên giây, dùng `math.floor(effective_timeout)` và **từ chối gọi** khi còn `< 1.0s` (không làm tròn lên vượt `remaining`); đồng thời kiểm tra `min_timeout=1.0` trước cả lazy import `rag.qdrant.client`.
     - **Cohere Rerank (`rag/rerank.py`):** truyền `timeout` và `request_options={"timeout_in_seconds": ..., "max_retries": 0}`; nếu còn `< 0.5s` thì bỏ qua Cohere và chạy heuristic cục bộ.
     - **Tavily (`integrations/tavily.py`):** truyền `timeout=effective_timeout` vào `client.search`; nếu còn `< 0.5s` thì bỏ qua.
     - **PostgreSQL (`persistence/database.py`):** thêm `pool_timeout`, `connect_timeout`, `statement_timeout` cho cấu hình PostgreSQL.
     - **Valkey/Redis (`core/cache.py`):** single-flight daemon probe có giới hạn `CACHE_REDIS_CONNECT_TIMEOUT_SECONDS` (mặc định `1.0s`) và cập nhật `_redis_last_attempt` sau khi probe xong, tránh OS `getaddrinfo` chặn request tới 30s.
  5. **Celery async chat (`api/app.py`, `jobs/tasks.py`):**
     - Dispatch gửi kèm `expires=CELERY_QUEUE_EXPIRES_SECONDS` (mặc định 55s) và `deadline_epoch`.
     - Task `llm_handle_message` đặt `soft_time_limit=50`, `time_limit=60`; khi worker nhận task sẽ tính thời gian còn lại từ `deadline_epoch` (nếu đã hết hạn trong hàng đợi thì trả degraded timeout ngay, không gọi LLM/RAG).
     - `GET /chat/complete/{task_id}` dùng `time.monotonic()`, trần poll `<= 55s`, và offload `AsyncResult` status/result lookup sang làn `probe` để không chặn event loop.

---

## 3. Chính sách Retry và Fallback

- **Một tầng điều phối retry:** SDK auto-retry bị tắt (`max_retries=0` trên OpenAI, Cohere, Zep). Retry chỉ được điều phối bởi tầng ứng dụng (`composer.py` tối đa `AGENT_MAX_COMPOSER_CALLS`, `rag.py` tối đa `AGENT_MAX_RETRIEVAL_CALLS`).
- **Phân loại lỗi (`retryable_llm_error`):**
  - **Không retry:** `BudgetExhaustedError`, `PermissionError`, `TypeError`, `KeyError`, các lỗi 4xx (`400`, `401`, `403`, `404`, `409`, `422`), `AuthenticationError`, `BadRequestError`, `InvalidHealthInput`, `ValueError` không phải truncated/empty output.
  - **Có retry (khi còn budget):** `TimeoutError` (khác `BudgetExhaustedError`), `ConnectionError`, `429`, `502`, `503`, `504`, output rỗng/bị cắt (`truncated`).
- **Backoff trong budget:** dùng `RequestBudget.backoff_seconds(...)` sao cho sau khi ngủ vẫn còn đủ `reserve + min_after_sleep`; nếu không đủ thì dừng retry ngay.
- **Fallback provider:** giữ nguyên policy hiện có (chỉ fallback sang OpenAI khi `provider != "openai"` và có `OPENAI_API_KEY`, không hard-code model, không tạo provider mặc định mới). Fallback dùng **chung `effective_deadline`** với primary; không chạy nếu lỗi là `BudgetExhaustedError`/`ValueError` hoặc thời gian còn lại `< LLM_FALLBACK_MIN_TIMEOUT_SECONDS` (0,05s).

---

## 4. Cô lập Event Loop, Giới hạn Input, Rate / Concurrency / Queue & Bất biến Urgent (R03)

### 4.1 Tách biệt 3 cơ chế giới hạn và phạm vi triển khai

| Cơ chế | Module | Phạm vi (Scope) | Hành vi khi chạm ngưỡng | Ghi chú khi tăng `API_WORKERS` |
|---|---|---|---|---|
| **Rate limit** (tần suất request) | `backend/src/core/rate_limit.py` | **Toàn deployment** khi Valkey khả dụng (Lua script `INCR` + `EXPIRE` atomic); **per-process** khi dev không có Valkey | HTTP `429` + `Retry-After` (tiếng Việt an toàn); ở `production` nếu Valkey lỗi/offline thì **fail-closed `503`** | Nhất quán toàn cluster khi có Valkey |
| **Concurrency limit** (số tác vụ đang chạy thực) | `backend/src/core/execution.py` (`BoundedWorkLane`) | **Per-process** (mỗi Uvicorn worker có các `ThreadPoolExecutor` riêng) | Chuyển sang hàng đợi nếu còn chỗ; không bao giờ chạy quá `max_concurrency` thread thực | Tổng tải tối đa ≈ `API_WORKERS × max_concurrency` |
| **Queue bound** (số request chờ & thời gian chờ) | `backend/src/core/execution.py` (`BoundedWorkLane`) | **Per-process** | Hàng đợi đầy hoặc chờ quá `queue_timeout_seconds` -> HTTP `503` + `Retry-After` | Tách biệt rõ với concurrency limit |

### 4.2 Cô lập khỏi AnyIO default threadpool & Bất biến Urgent

- **Lý do dùng làn executor riêng:** Trong FastAPI, dependency đồng bộ như `get_current_user` chạy trên default threadpool dùng chung của AnyIO. Nếu các tác vụ chậm (`/search`, `/summarize`, chat thường, indexing, health probes) cũng chạy trên pool đó, khi pool đầy sẽ làm cả request `urgent` bị kẹt ở bước auth.
- **Cách triển khai:** Mọi tác vụ chậm được offload tường minh vào 5 làn `BoundedWorkLane` độc lập (`chat`, `search`, `summarize`, `indexing`, `probe`), hoàn toàn tách khỏi AnyIO default threadpool.
- **Đường `urgent`:**
  1. Xác thực danh tính qua `Depends(get_current_user)` (pool AnyIO luôn rảnh).
  2. Chạy deterministic `check_medical_safety(...)` ngay đầu `/agent/answer` và `/chat/complete`.
  3. Khi `risk_level == "urgent"`: **bỏ qua** rate limiter (không chạm Valkey), **bỏ qua** hàng đợi/làn `chat`, **bỏ qua** DB/history/Celery/LLM/RAG/rerank/web; thực thi fast-path in-memory trực tiếp.
- **Chính sách truy cập & giới hạn input:**
  - `AUTH_MODE=production`: `/search` và `/summarize` yêu cầu xác thực (`401` nếu thiếu Authorization) trừ khi bật `ALLOW_PUBLIC_EXPENSIVE_ENDPOINTS=true`.
  - Giới hạn đầu vào tại boundary (trả `422` trước khi gọi provider): `/search` query `1..500` ký tự (không chỉ khoảng trắng), `/summarize` text `1..12000` ký tự, `/documents/index` & `/data/import` tối đa `50` doc và `250.000` ký tự/lô, `/tools/safety` tối đa `4000` ký tự.

### 4.3 Hành vi Timeout, Cancellation và Công việc Còn Chạy

- `asyncio.wait_for` hoặc client disconnect không thể cưỡng bức dừng tức thời một thread Python đang chặn trong I/O đồng bộ.
- **Cơ chế kiểm soát trong `BoundedWorkLane`:**
  1. Khi HTTP timeout hoặc client hủy kết nối (`CancelledError`): đánh dấu `cancel_event.set()`, tăng bộ đếm `abandoned`, trả `504` (hoặc dừng response) ngay cho client, nhưng **KHÔNG giải phóng execution permit sớm**.
  2. Permit chỉ được giải phóng **đúng một lần** (qua cờ `released` + lock) trong khối `finally:` của worker thread khi transport thực sự kết thúc (đảm bảo bởi transport timeout hữu hạn).
  3. Nhờ vậy, số worker thực đang chạy không bao giờ vượt `max_concurrency`, không thể tạo vô hạn thread thay thế, và sau khi worker cũ kết thúc thì permit được thu hồi sạch (không rò permit).
  4. Các stage sau trong graph/chat kiểm tra `cancel_event` và `deadline_monotonic`, không khởi chạy bước tiếp theo và không ghi nhận lượt bị hủy như hoàn thành bình thường.
- **Giới hạn đã ghi rõ:** Nếu một thư viện đồng bộ bên thứ ba bỏ qua socket timeout hoặc treo ở mức C/OS syscall, thread đó vẫn giữ 1 slot cho đến khi syscall thoát; tuy nhiên nó không bao giờ gây nhân bản thread vượt `max_concurrency` hay làm nghẽn `urgent`.

---

## 5. Biến Cấu hình Mới và Giá trị Mặc định

| Biến môi trường | Mặc định | Trần / Ghi chú |
|---|---|---|
| `AGENT_MAX_REQUEST_TIMEOUT_SECONDS` | `55` | Trần cứng server-side (`5..55s`) dưới gate 60s |
| `AGENT_MIN_CALL_TIMEOUT_SECONDS` | `0.25` | Ngưỡng tối thiểu để dispatch 1 call |
| `AGENT_RETRY_BACKOFF_SECONDS` | `0.2` | Delay backoff cơ sở (bị cắt theo remaining budget) |
| `LLM_FALLBACK_MIN_TIMEOUT_SECONDS` | `0.05` | Ngưỡng tối thiểu để cho phép fallback sang OpenAI |
| `CUSTOM_EMBEDDING_TIMEOUT_SECONDS` | `30` | Timeout mặc định khi không truyền deadline |
| `WEB_SEARCH_TIMEOUT_SECONDS` / `TAVILY_TIMEOUT_SECONDS` | `10` | Budget tác vụ web search |
| `RERANK_TIMEOUT_SECONDS` / `COHERE_RERANK_TIMEOUT_SECONDS` | `5` | Budget tác vụ Cohere rerank (min `0.5s`) |
| `SEARCH_TIMEOUT_SECONDS` / `SUMMARIZE_TIMEOUT_SECONDS` / `INDEXING_TIMEOUT_SECONDS` / `HEALTH_PROBE_TIMEOUT_SECONDS` | `15` / `25` / `45` / `5` | Trần lần lượt `30s` / `45s` / `55s` / `10s` |
| `TASK_TIMEOUT_SECONDS` / `CELERY_QUEUE_EXPIRES_SECONDS` | `50` / `55` | Trần `55s` / `60s` cho async chat |
| `CELERY_TASK_SOFT_TIME_LIMIT_SECONDS` / `CELERY_TASK_TIME_LIMIT_SECONDS` | `50` / `60` | Giới hạn cứng worker Celery |
| `CHAT_MAX_CONCURRENCY` / `CHAT_MAX_QUEUE` / `CHAT_QUEUE_TIMEOUT_SECONDS` | `4` / `8` / `5.0` | Per-process lane `chat` |
| `SEARCH_MAX_CONCURRENCY` / `SEARCH_MAX_QUEUE` / `SEARCH_QUEUE_TIMEOUT_SECONDS` | `4` / `8` / `3.0` | Per-process lane `search` |
| `SUMMARIZE_MAX_CONCURRENCY` / `SUMMARIZE_MAX_QUEUE` / `SUMMARIZE_QUEUE_TIMEOUT_SECONDS` | `2` / `4` / `3.0` | Per-process lane `summarize` |
| `INDEXING_MAX_CONCURRENCY` / `INDEXING_MAX_QUEUE` / `INDEXING_QUEUE_TIMEOUT_SECONDS` | `1` / `2` / `3.0` | Per-process lane `indexing` |
| `PROBE_MAX_CONCURRENCY` / `PROBE_MAX_QUEUE` / `PROBE_QUEUE_TIMEOUT_SECONDS` | `4` / `4` / `2.0` | Per-process lane `probe` |
| `API_RATE_LIMIT_ENABLED` / `RATE_LIMIT_FAIL_CLOSED_IN_PRODUCTION` | `true` / `true` | Bật rate limit; fail-closed 503 ở production khi mất Valkey |
| `CHAT_RATE_LIMIT_PER_MINUTE` / `SEARCH_RATE_LIMIT_PER_MINUTE` / `SUMMARIZE_RATE_LIMIT_PER_MINUTE` / `INDEXING_RATE_LIMIT_PER_MINUTE` | `30` / `30` (IP: `60`) / `10` (IP: `20`) / `10` | Cửa sổ 60 giây |
| `ALLOW_PUBLIC_EXPENSIVE_ENDPOINTS` | `false` | `false` = production yêu cầu auth cho `/search`, `/summarize` |
| `SEARCH_MAX_QUERY_CHARS` / `SUMMARIZE_MAX_TEXT_CHARS` / `INDEX_MAX_BATCH_DOCS` / `INDEX_MAX_BATCH_CHARS` | `500` / `12000` / `50` / `250000` | Giới hạn kích thước input |
| `CACHE_REDIS_CONNECT_TIMEOUT_SECONDS` / `CACHE_REDIS_SOCKET_TIMEOUT_SECONDS` / `CACHE_REDIS_RETRY_SECONDS` | `1.0` / `1.0` / `15` | Bound probe Valkey |
| `DB_POOL_TIMEOUT_SECONDS` / `DB_CONNECT_TIMEOUT_SECONDS` / `DB_STATEMENT_TIMEOUT_MS` | `5` / `5` / `10000` | Bound PostgreSQL pool/connect/query |

---

## 6. Danh sách File Thay đổi

### File mới
1. `backend/src/core/execution.py` — Làn thực thi `BoundedWorkLane` (dedicated `ThreadPoolExecutor`, bounded queue, abandoned worker accounting).
2. `backend/src/core/rate_limit.py` — Rate limiter tách biệt (atomic Valkey Lua script + fail-closed production + per-process dev fallback).
3. `backend/tests/unit/test_phase03_deadline_and_load.py` — 17 regression test cho R02 & R03 (budget, transport, retry/fallback, lazy init, Qdrant floor, event loop, admission, abandonment, cancellation, rate limit, urgent under saturation, medical caution).
4. `docs/reports/upgrade-2026/phase03-deadline-load-2026-11-18.md` — Báo cáo bàn giao Đợt 3.

### File đã sửa
5. `backend/src/harness/budget.py`
6. `backend/src/core/cache.py`
7. `backend/src/persistence/database.py`
8. `backend/src/llm/client.py`
9. `backend/src/llm/embedding.py`
10. `backend/src/llm/summarizer.py`
11. `backend/src/rag/qdrant/client.py`
12. `backend/src/rag/search.py`
13. `backend/src/rag/rerank.py`
14. `backend/src/rag/query_rewriter.py`
15. `backend/src/integrations/tavily.py`
16. `backend/src/memory/zep_memory.py`
17. `backend/src/memory/sync.py`
18. `backend/src/memory/chat.py`
19. `backend/src/jobs/tasks.py`
20. `backend/src/agents/constants.py`
21. `backend/src/agents/state.py`
22. `backend/src/agents/context.py`
23. `backend/src/agents/graph.py`
24. `backend/src/agents/composer.py`
25. `backend/src/agents/nodes/normalize.py`
26. `backend/src/agents/nodes/supervisor.py`
27. `backend/src/agents/nodes/rag.py`
28. `backend/src/agents/nodes/web_search.py`
29. `backend/src/api/app.py`
30. `docs/implementation-roadmap/README.md`

---

## 7. Kết quả Kiểm thử & Số đo HTTP

### 7.1 Unit, Fast-Path Integration & Syntax

| Hạng mục | Lệnh / Phạm vi | Kết quả |
|---|---|---|
| Backend unit + fast-path integration | `$env:PYTHONPATH=(Resolve-Path 'backend/src').Path; $env:DATABASE_URL='sqlite://'; python -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider` | **308 passed**, 0 failed (291 nền cũ + 17 test Đợt 3 mới; 2 cảnh báo `on_event` cũ) |
| Cú pháp & Python 3.10 grammar (`backend` image target) | `py_compile` + `ast.parse(..., feature_version=(3, 10))` trên 28 file sửa/mới | **PASS (28/28 files)** |
| Diff whitespace hygiene | `git diff --check -- backend/ docs/` | **PASS (0 issues)** |

### 7.2 Kiểm chứng HTTP: **HTTP backend thật, upstream giả để fault injection**

- **Môi trường:** tiến trình Uvicorn thật chạy `api.app:app` bind `127.0.0.1` trên cổng trống riêng + HTTP server giả loopback (`127.0.0.1`) mô phỏng Ollama/Embedding/Qdrant có độ trễ và lỗi chủ động + SQLite tạm cô lập (`AUTH_MODE=development`, `BM25_AUTOLOAD=false`). Toàn bộ tiến trình và artifact tạm đã được dừng và dọn sau khi đo.
- **Lưu ý phạm vi:** Đây là **HTTP backend thật, upstream giả để fault injection**, không phải benchmark production E2E với GPU/Ollama/Qdrant/PostgreSQL/Valkey thật.

| Ca kiểm thử | Tải & Cấu hình | Status HTTP | Số mẫu & Độ trễ (wall time từ HTTP client) | Xác minh phía server / upstream |
|---|---|---|---|---|
| **Ca 1 — Provider chậm trong budget** | `/summarize`, `SUMMARIZE_TIMEOUT_SECONDS=1.0`, upstream trễ `4000 ms` | `504` | N=1, wall time **1260,56 ms** (dung sai ~260 ms cho HTTP/scheduling trên Windows; không chờ 4s hay 60s) | Trả thông báo tiếng Việt an toàn, không lộ chi tiết provider |
| **Ca 2 — Retry trong cùng budget** | `/agent/answer` (nhánh Composer gọi Ollama), `AGENT_REQUEST_TIMEOUT_SECONDS=2.4`, upstream trả `503` sau `850 ms` | `200` (`status="degraded"`) | N=1, wall time **2037,90 ms** (`< 2400 ms`) | Upstream nhận đúng **2 call** (1 chính + 1 retry) trong cùng deadline |
| **Ca 3 — Urgent & BMI dưới tải chậm đồng thời** | Song song 2 `/search` chậm (1680 ms, 1695 ms -> `504`) + 1 `/summarize` chậm (1113 ms -> `200`); bắn đồng thời **N=25 urgent** + **N=10 BMI** | Urgent: 25/25 `200`; BMI: 10/10 `200` | **Urgent (N=25):** P50 **1,42 ms**, P95 **2,01 ms**, max **23,19 ms** (`< 500 ms`). **BMI (N=10):** P50 **2,93 ms**, P95 **3,49 ms**, max **3,49 ms** | **0 call** tới Ollama và **0 call** tới Embedding phát sinh từ 35 request fast-path |
| **Ca 4 — Admission đầy trả 503** | 6 `/search` đồng thời, `max_concurrency=2`, `max_queue=1`, `queue_timeout=0.4s`, upstream trễ `900 ms` | 2× `200`, 4× `503` | N=6 đồng thời | Upstream `/embed` chỉ nhận **2 call**, `max_concurrent=2`; 4 request bị từ chối không chạm upstream |
| **Ca 5 — Timeout / disconnect & thu hồi permit** | `/summarize` `max_concurrency=1, max_queue=0, timeout=1.0s`: (a) timeout server `1.0s`; (b) client ngắt sớm ở `0.30s` khi worker chạy `0.90s`; (c) gọi thử ngay khi worker cũ còn chạy; (d) gọi lại sau khi worker kết thúc | (a) `504`; (c) `503`; (d) `200` | N=4 tuần tự theo pha | `max_concurrent_upstream_ollama = 1` (không vượt limit khi bị disconnect), permit phục hồi 100% ở (d) |
| **Ca 6 — Lỗi dependency, 422 validation, 429 rate limit, `/health`** | Upstream `500` ở Composer; BMI âm; `/search` > 200 ký tự; `/summarize` > 500 ký tự; 5 request `/summarize` liên tiếp với limit `4/phút` | BMI âm `422`, search/summarize quá dài `422`, `/health` `200`, Composer upstream 500 -> `200` (`status="degraded"`), rate limit `[200,200,200,200,429]` (`Retry-After: 60`) | N=5 cho rate limit | Request thứ 5 bị chặn `429` trước upstream (`upstream_calls = 4`) |

---

## 8. Dependency Thật / Giả và Phần Chưa Kiểm chứng

- **Đã kiểm chứng thật:** FastAPI/Starlette/Uvicorn event loop, TCP/HTTP loopback, Pydantic validation, `BoundedWorkLane` threadpool/queue/abandonment, `RequestBudget` end-to-end, `requests`/`httpx`/`openai` timeout options.
- **Dùng giả / chưa kiểm chứng runtime thật:**
  - Chưa chạy với Docker Compose, PostgreSQL thật, Valkey thật, Qdrant thật, BGE-M3 embedding thật, Ollama GPU thật, Cohere API thật, Tavily API thật hoặc Celery worker thật.
  - Chưa đo soak test dài hạn hoặc hành vi multi-worker (`API_WORKERS > 1`) với Valkey cluster thật.
  - Chưa triển khai/restart bất kỳ container nào của hệ thống hiện hữu.

---

## 9. Rủi ro Còn lại và Hướng Rollback

### Rủi ro còn lại
1. **Thư viện đồng bộ bỏ qua timeout ở mức OS/C:** `BoundedWorkLane` bảo vệ không cho vượt `max_concurrency` và không chặn `urgent`, nhưng nếu nhiều thread bị treo sâu trong syscall không có timeout, làn tương ứng sẽ trả `503` cho đến khi syscall thoát.
2. **Đặt ngưỡng `AGENT_REQUEST_TIMEOUT_SECONDS` quá thấp trên GPU 4 GB:** Nếu model local phản hồi chậm hơn reserve (15s), một số câu phức tạp có thể rơi vào degraded fallback sớm hơn kỳ vọng — cần hiệu chỉnh lại các biến reserve/timeout khi benchmark trên GPU 4 GB thật.
3. **Production không có Valkey:** Do rate limit production fail-closed `503`, mất Valkey sẽ chặn `/search`, `/summarize`, chat không khẩn cấp (đường `urgent` vẫn hoạt động bình thường); có thể tạm thời đặt `RATE_LIMIT_FAIL_CLOSED_IN_PRODUCTION=false` để chuyển về per-process khi xử lý sự cố hạ tầng.
4. **Thay đổi auth `/search` & `/summarize` ở `production`:** Các client không gửi Bearer token trong `AUTH_MODE=production` nay nhận `401` (UI frontend hiện đã gửi `getRequestHeaders()`). Nếu có caller cũ cần mở tạm thời, cấu hình `ALLOW_PUBLIC_EXPENSIVE_ENDPOINTS=true` (vẫn có rate limit theo IP).

### Hướng rollback
- Toàn bộ thay đổi nằm gọn trong `backend/src/` và `backend/tests/unit/test_phase03_deadline_and_load.py`, không thay đổi database schema, Qdrant collection, hay frontend contract.
- Có thể rollback cấu hình nóng qua biến môi trường (`API_RATE_LIMIT_ENABLED=false`, `ALLOW_PUBLIC_EXPENSIVE_ENDPOINTS=true`, nâng `*_MAX_CONCURRENCY`/`*_TIMEOUT_SECONDS`) hoặc revert toàn bộ diff Đợt 3 bằng `git` về revision `4e64f97` mà không ảnh hưởng dữ liệu hay Đợt 1/Đợt 2.

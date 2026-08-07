# Kế hoạch tái cấu trúc `backend/src`

**Trạng thái:** Đề xuất chờ duyệt  
**Ngày:** 07/08/2026  
**Phạm vi:** Chỉ tổ chức lại mã nguồn backend; không thay đổi hành vi Agent,
LLM, retrieval hoặc dữ liệu Qdrant nếu phase đó chưa được kiểm thử đạt.

## 1. Mục tiêu

- Giảm số lượng module nằm trực tiếp trong `backend/src`.
- Tách rõ API, Agent, LLM, RAG/Qdrant, dữ liệu nghiệp vụ và job nền.
- Giữ hệ thống chạy được trong suốt quá trình di chuyển bằng compatibility
  wrapper.
- Có kiểm thử bắt buộc sau từng phase.
- Có thể rollback từng phase bằng cách khôi phục wrapper hoặc revert patch nhỏ.

## 2. Cây thư mục đích

```text
backend/src/
├── __init__.py
├── app.py                         # wrapper tạm: uvicorn app:app
├── tasks.py                       # wrapper tạm cho Celery
├── agent.py                       # wrapper/legacy tạm
│
├── api/
│   ├── __init__.py
│   ├── app.py                     # FastAPI app và lifecycle
│   ├── routes.py                  # HTTP routes
│   └── schemas.py                 # Pydantic request/response
│
├── agents/
│   ├── __init__.py
│   ├── graph.py                   # Agent graph chính
│   ├── state.py
│   └── parsing.py
│
├── core/
│   ├── __init__.py
│   ├── config.py                  # từ configs.py
│   ├── logging.py                 # phần logging từ utils.py
│   ├── cache.py
│   └── errors.py
│
├── llm/
│   ├── __init__.py
│   ├── client.py                  # từ brain.py
│   ├── embedding.py               # từ custom_embedding.py
│   └── summarizer.py
│
├── rag/
│   ├── __init__.py
│   ├── search.py
│   ├── query_rewriter.py
│   ├── rerank.py
│   ├── splitter.py
│   ├── metadata.py                # từ vector_metadata.py
│   └── qdrant/
│       ├── __init__.py
│       ├── client.py              # từ vectorize.py
│       ├── collection_admin.py
│       └── naming.py
│
├── health/
│   ├── __init__.py
│   ├── tools.py                   # từ health_tools.py
│   └── legal_tools.py
│
├── persistence/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── personalization.py
│
├── integrations/
│   ├── __init__.py
│   └── tavily.py                  # từ tavily_tool.py
│
├── jobs/
│   ├── __init__.py
│   └── tasks.py
│
└── pipelines/
    ├── __init__.py
    ├── import_data.py
    ├── import_missing_vectors.py
    └── reuse_qdrant_vectors.py
```

## 3. Quy tắc triển khai

1. Mỗi phase dùng một patch nhỏ, không gộp nhiều nhóm thay đổi.
2. Không xóa file cũ ngay sau khi tạo file mới; giữ wrapper cho tới khi runtime
   và test đã chạy ổn định ít nhất một phase kế tiếp.
3. Dùng import tuyệt đối theo package mới; không dùng import vòng.
4. Không đổi tên biến môi trường, API contract hoặc tên model trong lúc chỉ tổ
   chức lại thư mục.
5. Không restart backend/embedding khi còn bulk import hoặc job Qdrant.
6. Không xóa, recreate hoặc đổi alias Qdrant trong task tái cấu trúc source.
7. Nếu một phase làm hỏng health, test hoặc import, dừng phase đó và rollback;
   không tiếp tục di chuyển các phase sau.

## 4. Các phase và quality gate

### Phase 0 — Chụp baseline và khóa phạm vi

**Mục tiêu:** ghi nhận trạng thái trước khi di chuyển.

**Công việc:**

- Kiểm tra `git status --short` và diff hiện có.
- Lập danh sách import/call path từ `backend/src`.
- Ghi lại LLM provider/model, collection alias, point count và trạng thái
  embedding.
- Không sửa logic nghiệp vụ.

**Kiểm thử bắt buộc:**

```powershell
$env:PYTHONPATH=(Resolve-Path 'backend/src').Path
python -m pytest backend/tests/unit -q -p no:cacheprovider
python -m py_compile backend/src/*.py backend/src/agents/*.py
docker compose -f backend/docker-compose.yml config
docker compose -f embed_serving/docker-compose.serving.yml config
```

**Quality gate:** baseline lưu được; unit test, compile và compose validation
đạt; Qdrant alias/point count không thay đổi.

### Phase 1 — Tạo package và compatibility layer

**Mục tiêu:** tạo các thư mục đích mà chưa đổi hành vi.

**Công việc:**

- Tạo `__init__.py` cho package.
- Tạo wrapper `app.py`, `tasks.py`, `agent.py` giữ entrypoint hiện tại.
- Chưa di chuyển implementation lớn.

**Kiểm thử bắt buộc:**

- Import smoke toàn bộ package bằng Python.
- `python src/import_data.py --help` và các CLI admin `--help`.
- `py_compile` toàn bộ file mới và wrapper.
- Không có import vòng.

**Quality gate:** `uvicorn app:app` và Celery command vẫn khởi động được;
không thay đổi response API.

### Phase 2 — Tách `core` và `api`

**Mục tiêu:** tách cấu hình, logging, cache và HTTP boundary.

**Di chuyển dự kiến:**

- `configs.py` → `core/config.py`.
- phần logging của `utils.py` → `core/logging.py`.
- `cache.py` → `core/cache.py`.
- phần FastAPI/Pydantic của `app.py` → `api/app.py`, `api/routes.py`,
  `api/schemas.py`.
- Root `app.py` chỉ re-export `api.app:app`.

**Kiểm thử bắt buộc:**

- Unit test hiện tại.
- `python -m py_compile` các module core/api.
- `GET /health` qua HTTP thật.
- Greeting, BMI hợp lệ, input âm trả HTTP 422.

**Quality gate:** status/response contract không đổi; backend health healthy;
chưa được coi là deploy hoàn tất nếu chỉ test trong process.

### Phase 3 — Tách `agents` và `llm`

**Mục tiêu:** phân biệt orchestration Agent với provider LLM/embedding.

**Di chuyển dự kiến:**

- `brain.py` → `llm/client.py`.
- `custom_embedding.py` → `llm/embedding.py`.
- `summarizer.py` → `llm/summarizer.py`.
- `agents/graph.py`, `state.py`, `parsing.py` giữ trong package `agents`.
- `agent.py` chỉ còn compatibility wrapper, chưa xóa.

**Kiểm thử bắt buộc:**

- Mock LLM và retrieval trong greeting, BMI và urgent safety.
- Chứng minh fast-path không gọi LLM, Qdrant hoặc embedding.
- Kiểm tra `LLM_PROVIDER`, model và `OLLAMA_THINK` vẫn lấy từ environment.
- Test HTTP urgent safety và BMI.

**Quality gate:** safety fast-path không tăng latency đáng kể; không hard-code
model; Agent trace và response contract không đổi.

### Phase 4 — Tách RAG và Qdrant

**Mục tiêu:** gom toàn bộ retrieval/vector logic vào `rag`.

**Di chuyển dự kiến:**

- `search.py`, `query_rewriter.py`, `rerank.py`, `splitter.py` → `rag/`.
- `vectorize.py`, `vector_metadata.py`, `collection_naming.py`,
  `qdrant_collection_admin.py` → `rag/qdrant/`.

**Kiểm thử bắt buộc:**

- Qdrant alias `nmk_chatbot_active` vẫn có 23.608 point, `green`, optimizer ok.
- Không thay đổi payload hoặc vector dimension.
- Retrieval smoke cho InBody, nutrition, exercise và medical safety.
- Citation phải trỏ tới document thật.
- Không gọi RAG trong tool-only query và urgent fast-path.

**Quality gate:** retrieval qua alias thành công; point count trước/sau giống
nhau; không có thao tác import, delete hoặc recreate collection.

### Phase 5 — Tách persistence, health và integrations

**Mục tiêu:** tách nghiệp vụ sức khỏe, database và dịch vụ bên ngoài.

**Di chuyển dự kiến:**

- `health_tools.py`, `legal_tools.py` → `health/`.
- `database.py`, `models.py`, `personalization.py` → `persistence/`.
- `tavily_tool.py` → `integrations/tavily.py`.

**Kiểm thử bắt buộc:**

- PostgreSQL connection/health check.
- Personalization không làm lộ dữ liệu chéo user.
- Safety regression test đầy đủ.
- Tavily lỗi phải trả degraded có chủ đích, không lộ stack trace.

**Quality gate:** không đổi schema database; không log PII không cần thiết;
safety cảnh báo vẫn được giữ trong câu trả lời cuối.

### Phase 6 — Tách jobs và pipelines

**Mục tiêu:** tách worker runtime khỏi các CLI import/migration.

**Di chuyển dự kiến:**

- `tasks.py` → `jobs/tasks.py`.
- `import_data.py`, `import_missing_vectors.py`,
  `reuse_qdrant_vectors.py` → `pipelines/`.
- Root `tasks.py` và các CLI root giữ wrapper tương thích.

**Kiểm thử bắt buộc:**

- Celery worker khởi động và nhận task test không phá dữ liệu.
- CLI `--help`, dry-run và validation.
- Kiểm tra manifest/checkpoint idempotent.
- Không chạy bulk import thật trong phase tái cấu trúc.

**Quality gate:** worker không import nhầm module API; CLI không ghi Qdrant khi
chạy dry-run; không có process import nền trước khi restart.

### Phase 7 — Cập nhật Docker entrypoint và deploy kiểm soát

**Mục tiêu:** bỏ dần phụ thuộc vào module phẳng.

**Công việc:**

- Chuyển entrypoint sang `api.app:app` và `jobs.tasks.celery_app` sau khi wrapper
  đã được kiểm chứng.
- Cập nhật `PYTHONPATH`, Docker compose và README.
- Recreate riêng API/worker; không restart Qdrant nếu không cần.

**Kiểm thử bắt buộc:**

- `docker compose ... config` cho backend, embedding và frontend.
- `GET /health` sau recreate.
- HTTP smoke: greeting, BMI, urgent safety, InBody, nutrition, exercise,
  safety retrieval và input âm.
- Kiểm tra logs không có `ModuleNotFoundError`, traceback hoặc secret.

**Quality gate:** runtime thật nhận code mới; tất cả smoke test đạt; không chỉ
dựa vào TestClient hoặc test trong process.

### Phase 8 — Dọn wrapper và chốt tài liệu

**Mục tiêu:** chỉ xóa module cũ khi hệ thống đã ổn định.

**Công việc:**

- Xóa wrapper/legacy module không còn consumer.
- Cập nhật cây thư mục, README, `AGENTS.md` và tài liệu vận hành.
- Ghi số liệu trước/sau: test, latency, health, collection alias.

**Kiểm thử bắt buộc:**

```powershell
$env:PYTHONPATH=(Resolve-Path 'backend/src').Path
python -m pytest backend/tests/unit -q -p no:cacheprovider
git diff --check
docker compose -f backend/docker-compose.yml config
```

Sau đó chạy lại toàn bộ HTTP smoke test và kiểm tra container không restart
liên tục.

**Quality gate:** không còn import tới module cũ; không còn P0/P1 mới; tài liệu
phản ánh đúng runtime hiện tại.

## 5. Điều kiện dừng và rollback

Dừng ngay phase hiện tại nếu xảy ra một trong các trường hợp:

- backend health không healthy;
- HTTP contract thay đổi ngoài chủ đích;
- safety fast-path gọi LLM/RAG;
- Qdrant point count, alias hoặc payload bị thay đổi ngoài kế hoạch;
- xuất hiện import vòng hoặc `ModuleNotFoundError`;
- worker/API restart liên tục.

Rollback phase chỉ khôi phục patch của phase đó và giữ nguyên dữ liệu Qdrant.
Không dùng `git reset --hard`, không xóa collection để sửa lỗi import module.

## 6. Definition of Done

Tái cấu trúc chỉ được coi là hoàn tất khi:

- cây thư mục mới được áp dụng đầy đủ;
- compatibility wrapper không còn consumer hoặc đã được xóa có kiểm chứng;
- unit, compile, compose và HTTP smoke test đều đạt;
- backend/worker runtime đã recreate và nhận code mới;
- Qdrant alias/point count không bị thay đổi ngoài kế hoạch;
- không có regression safety, cross-user data leak hoặc hard-code model;
- tài liệu triển khai và số liệu trước/sau đã cập nhật.

## 7. Nhật ký triển khai

| Ngày | Phase | Thay đổi | Unit | HTTP | Runtime | Ghi chú |
|---|---|---|---:|---|---|---|
| 07/08/2026 | 0 | Baseline trước tái cấu trúc; HEAD `b6b5da9` | 23 passed | Backend/embedding healthy | Alias `nmk_chatbot_active`, 23.608 point, green | Đạt; chưa di chuyển logic |
| 07/08/2026 | 1 | Tạo package shell và `__init__.py`; không đổi entrypoint/logic | 23 passed; container import/compile đạt | Backend healthy | Qdrant không đổi | Đạt; host thiếu `psycopg2`/`qdrant_client`, đã xác nhận bằng container runtime |
| 07/08/2026 | 2 | `app`, `configs`, `cache`, `utils` chuyển vào `api/` và `core/`; root wrapper giữ entrypoint | 23 passed; import/compile đạt | Backend healthy | Alias/point count không đổi | Đạt; chưa tách router vật lý |
| 07/08/2026 | 3 | `brain`, embedding adapter và summarizer chuyển vào `llm/`; module alias giữ private API cũ | 23 passed; import/compile đạt | Backend healthy; LLM `ollama/qwen3:8b` | Qdrant không đổi | Đạt; không đổi provider/model contract |

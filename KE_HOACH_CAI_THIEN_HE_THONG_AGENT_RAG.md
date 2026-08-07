# Kế hoạch cải thiện hệ thống Health/InBody Agent RAG

**Ngày lập:** 30/07/2026  
**Căn cứ:** `BAO_CAO_KIEM_THU_HE_THONG_2026-07-30.md`  
**Mục tiêu:** đưa hệ thống từ MVP/dev demo lên mức Agent RAG beta có thể kiểm thử với người dùng nội bộ, sau đó mới xét production.

---

## 0. Tiến độ triển khai

**Cập nhật 07/08/2026, sau khi hoàn tất import Qdrant v2**

### Đợt 1 — P0 Agent

- [x] Tạo regression test cho Ollama payload, router, safety, greeting và BMI.
- [x] Chuyển model/provider sang cấu hình hoàn toàn bằng môi trường.
- [x] Thêm `OLLAMA_THINK=auto|true|false`; không hard-code model-specific behavior trong Agent.
- [x] Thêm task budget riêng cho router, normalize, rewrite và composer.
- [x] Thêm safety fast-path không gọi LLM/RAG.
- [x] Thêm greeting và BMI fast-path.
- [x] Chuẩn hóa routing có dấu/không dấu.
- [x] Thêm validation HTTP 422 cho chỉ số không hợp lệ.
- [x] Mở rộng response với `status`, `fast_path`, `errors`, `tool_results`, `safety_result`, `latency_ms`.
- [x] Unit test hiện tại: 22/22 đạt.
- [x] Integration test trong process container:
  - greeting: 0,82 ms;
  - urgent safety: 0,23 ms;
  - BMI: 2,23 ms.
- [x] Recreate riêng backend API/worker sau khi xác nhận import đã dừng và
  Qdrant update queue bằng 0.
- [x] HTTP runtime đã nạp `OLLAMA_THINK=false`.
- [x] Thêm deadline tổng 30 giây, retrieval mặc định một query gốc, timeout
  embedding query 10 giây và Qdrant search 5 giây.
- [ ] LLM composer đạt chất lượng/latency.

Ca RAG “BMI, PBF và SMM khác nhau như thế nào?” đã giảm từ hơn 65 giây xuống
23,30 giây backend, nhưng vẫn `degraded` vì Qwen3 8B timeout sau 20 giây.
`ollama ps` cho thấy model 6,0 GB đang chạy 61% CPU/39% GPU trên RTX 3050
4 GB. Ngay cả benchmark trực tiếp 64/96 token cũng timeout khi hàng đợi Ollama
đang bận. Do đó deadline đã hoạt động nhưng chưa thể đánh dấu composer đạt.

### Đợt 2 — dữ liệu và Qdrant v2

- [x] Không ghi đè `content_type` do data pipeline cung cấp.
- [x] Thêm schema payload `document_id`, `corpus_version`, `content_hash`.
- [x] Import dùng stable UUID, manifest atomic, checksum và `--start-line`.
- [x] Lỗi upsert Qdrant trở thành fatal error, không tiếp tục báo thành công giả.
- [x] Thêm CLI create/verify/index/alias có point-count gate.
- [x] Tạo collection
  `nmk_chatbot_collection_v20260730_bge_m3_1024`: vector size 1024, trạng thái
  green và đủ 10 payload index.
- [x] Build image embedding GPU FP16.
- [ ] Deploy embedding GPU FP16: bị chặn bởi Docker Desktop 4.26.1/WSL CUDA
  `Error 500: named symbol not found`.
- [x] Dry-run lại corpus bằng source mới: 5.345 document, 23.608 chunk,
  checksum `1a474bf5...c8665eea`, 0 lỗi.
- [x] Import đủ 23.608 point vào collection v2; collection green, optimizer `ok`,
  `error_count=0`, không còn tiến trình import.
- [ ] Chạy retrieval benchmark chính thức trên alias `nmk_chatbot_active`.

Alias `nmk_chatbot_active` hiện trỏ tới collection v2; backend đã recreate và
health xác nhận dùng alias. Collection cũ `nmk_chatbot_collection` đã được xóa
theo yêu cầu sau khi chuyển runtime thành công. Import dùng embedding BGE-M3 CPU
(`float32`, batch 8); service healthy và `cuda_available=false`. Manifest cuối nằm tại
`backend/artifacts/imports/2026-08-06-v2-cross-batch-import.json`. Quy trình
blue/green và bước benchmark trước chuyển alias nằm tại
`docs/QDRANT_BLUE_GREEN_IMPORT.md`.

### Các đợt sau

- [ ] Đợt 3: dense+sparse hybrid, intent filter, reranker gate và RAG eval.
- [ ] Đợt 4: GPU benchmark, UI, auth, security và observability.

---

## 1. Kết quả cần đạt

Sau khi hoàn thành kế hoạch, hệ thống phải:

1. Trả cảnh báo cấp cứu dưới 500 ms, không phụ thuộc LLM hoặc RAG.
2. Không còn request Agent kéo dài trên 60 giây trong bộ test chuẩn.
3. Trả kết quả tool như BMI/PBF trong vài trăm mili giây.
4. Có corpus Qdrant hoàn chỉnh, đếm được, tái lập được và có version.
5. Thực hiện hybrid retrieval thật sự, không dùng BM25 global RAM theo worker.
6. Không đưa tài liệu nutrition/recipe vào câu hỏi medical safety.
7. Có bộ benchmark có ground truth thay cho đánh giá cảm tính.
8. Có UI phản hồi rõ, an toàn khi render dữ liệu và không lộ màn hình dev ở production.
9. Có auth, phân quyền, audit log và bảo vệ dữ liệu sức khỏe trước khi public.
10. Có quy trình deploy/rollback không làm mất collection hiện hành.

---

## 2. Phạm vi và giả định

### 2.1 Phạm vi

- Backend FastAPI và LangGraph.
- Ollama/Qwen3.
- BGE-M3 embedding service.
- Qdrant và cơ chế hybrid retrieval.
- Health tools và safety guardrail.
- Frontend Streamlit.
- Test, benchmark, logging, bảo mật và vận hành.

### 2.2 Những việc chưa làm ngay

- Không huấn luyện/fine-tune LLM trong giai đoạn đầu.
- Không đổi toàn bộ framework Agent.
- Không tối ưu cho hàng nghìn người dùng đồng thời trước khi correctness đạt.
- Không tuyên bố hiệu quả y khoa hoặc dùng thay chuyên gia y tế.
- Không xóa collection đang chạy để import lại trực tiếp.

### 2.3 Giả định cần xác nhận

- 23.608 chunk là số lượng dự kiến của corpus hiện tại.
- Dữ liệu có quyền sử dụng và có thể truy vết nguồn.
- Máy triển khai chính là RTX 3050 Laptop 4 GB VRAM.
- Qwen3 8B và BGE-M3 hiện phải chia sẻ cùng GPU nếu cùng bật CUDA.
- Nhóm phát triển chấp nhận tạo collection mới và chuyển alias thay vì ghi đè collection cũ.

---

## 3. Thứ tự ưu tiên

```text
P0: Agent trả được và safety đúng thời gian
  ↓
P1: Dữ liệu hoàn chỉnh, retrieval đúng và đo được
  ↓
P1: UI không timeout, có observability
  ↓
P1: Auth, data isolation, hardening
  ↓
P2: Load test, tối ưu chi phí/tài nguyên, release beta
```

Không nên bắt đầu tinh chỉnh prompt hoặc reranker trước khi hoàn tất P0 và đóng băng một phiên bản corpus. Nếu dữ liệu tiếp tục thay đổi, các chỉ số accuracy trước/sau không so sánh được.

---

## 4. Roadmap tổng thể

| Giai đoạn | Nội dung | Ước lượng solo | Điều kiện kết thúc |
|---|---|---:|---|
| 0 | Đóng baseline và tạo safety net | 0,5–1 ngày | Có test tái hiện lỗi hiện tại |
| 1 | Hotfix LLM, routing, safety | 2–3 ngày | Agent không còn timeout trong smoke suite |
| 2 | Hoàn thiện dữ liệu và Qdrant v2 | 3–5 ngày | Collection khớp manifest, metadata sạch |
| 3 | Hybrid retrieval và đánh giá RAG | 3–5 ngày | Đạt KPI retrieval trên benchmark |
| 4 | Hiệu năng, GPU và UI | 2–4 ngày | Đạt KPI latency và UI functional |
| 5 | Bảo mật, observability, production hardening | 3–5 ngày | Không còn lỗi P0/P1 |
| 6 | Release candidate và nghiệm thu beta | 1–2 ngày | Toàn bộ quality gate đạt |

**Tổng ước lượng:** khoảng 14–25 ngày làm việc cho một người, đã gồm thời gian sửa lỗi nhưng chưa gồm thời gian xin duyệt dữ liệu/y khoa. Với 2–3 người làm song song sau giai đoạn 1, có thể rút xuống khoảng 2–3 tuần.

Ước lượng này không phải cam kết lịch. Nếu corpus có nhiều duplicate, nguồn không rõ hoặc GPU không đủ, giai đoạn dữ liệu/hiệu năng sẽ kéo dài.

---

## 5. Giai đoạn 0 — đóng baseline và tạo safety net

### BL-01 — Đóng băng bằng chứng hiện tại

**Thực hiện**

- Lưu report hiện tại.
- Ghi lại:
  - Git commit/working tree;
  - image/container version;
  - model Ollama và quantization;
  - embedding model/dimension;
  - Qdrant collection và point count;
  - corpus checksum;
  - cấu hình `.env` đã loại secret.
- Không dùng số liệu benchmark trong lúc import làm baseline cuối cùng.

**Artifact đề xuất**

```text
artifacts/baseline/2026-07-30/
  environment.json
  qdrant_collection.json
  latency.json
  agent_smoke.jsonl
```

**Nghiệm thu**

- Có thể xác định chính xác code, config, model và data nào tạo ra kết quả.

### BL-02 — Tạo test tái hiện lỗi P0

**File/thư mục dự kiến**

```text
backend/tests/unit/
backend/tests/integration/
backend/evals/
```

**Test bắt buộc**

1. Qwen3 router không được trả route rỗng.
2. BMI 72 kg/170 cm trả 24,91.
3. Đau ngực + khó thở trả `urgent`.
4. Ca `urgent` không được gọi query rewrite, Qdrant hoặc composer.
5. Câu không dấu “goi y lich tap...” vẫn chọn Training.
6. API đầu vào âm trả HTTP 422/400.
7. `/agent/answer` trả trace và errors nhất quán.

**Nghiệm thu**

- Test phải thất bại trên code cũ ở đúng lỗi đã quan sát.
- Sau mỗi hotfix, test trở thành regression guard.

---

## 6. Giai đoạn 1 — hotfix LLM, routing và safety

### HOT-01 — Sửa tích hợp Qwen3 thinking

**File chính**

- `backend/src/brain.py`
- `backend/.env.example`
- `backend/docker-compose.yml`

**Thay đổi**

1. Thêm capability config `OLLAMA_THINK=auto|true|false`:
   - `auto`: không gửi field `think`, tương thích model không có thinking;
   - `true`/`false`: gửi capability rõ ràng khi model hỗ trợ.
2. Runtime Qwen3 hiện tại cấu hình `OLLAMA_THINK=false` trong môi trường; không hard-code trong router/rewrite/composer.
3. Model và provider luôn lấy từ cấu hình; đổi model không yêu cầu sửa code.
4. Tạo profile theo tác vụ thay vì dùng chung `LLM_MAX_TOKENS=1024`.

**Cấu hình đề xuất**

| Tác vụ | `num_predict` | Temperature | Timeout |
|---|---:|---:|---:|
| Router | 8–16 | 0 | 5–8 giây |
| Follow-up normalization | 64–96 | 0 | 10 giây |
| Query rewrite | 64–128 | 0–0,1 | 10–15 giây |
| Response composer | 256–400 | 0,1–0,2 | 20–30 giây |
| Summary dài | 300–500 | 0–0,2 | 30–45 giây |

**Thiết kế API nội bộ đề xuất**

```python
chat_complete(
    messages,
    task="router",
    max_tokens=16,
    timeout=8,
)
```

Không nên chỉ đổi biến global từ 1.024 xuống một số nhỏ hơn; mỗi tác vụ cần budget riêng.

**Nghiệm thu**

- 100 lần router liên tiếp không có `content=""`.
- Router P95 dưới 3 giây khi hệ thống không import.
- Không có log `Invalid LLM route ''`.

**Rollback**

- Feature flag `OLLAMA_THINK=auto|true|false`.
- Giữ keyword fallback nếu Ollama lỗi.

### HOT-02 — Thiết lập ngân sách thời gian toàn request

**File chính**

- `backend/src/agents/graph.py`
- `backend/src/brain.py`
- `backend/src/query_rewriter.py`
- `backend/src/app.py`

**Thay đổi**

- Gắn `deadline` vào AgentState.
- Mỗi node kiểm tra thời gian còn lại.
- Không để từng node tự dùng đầy đủ timeout 60 giây.
- Bỏ qua rewrite/rerank/composer khi budget không đủ.
- Kiểm tra client disconnect nếu framework hỗ trợ.
- Trả `degraded=true` và lý do khi dùng fallback.

**Ngân sách đề xuất**

```text
Tool-only request:       1 giây
General chat:           15 giây
RAG chat:               20 giây
Hard timeout backend:   30 giây
```

**Nghiệm thu**

- Không request chuẩn nào vượt 30 giây ở backend.
- Client và backend timeout không bằng nhau; client phải lớn hơn backend 5–10 giây.
- Không còn trường hợp server tiếp tục chạy lâu sau khi client đã bỏ request.

### HOT-03 — Safety fast-path trước mọi LLM/RAG

**File chính**

- `backend/src/agents/graph.py`
- `backend/src/health_tools.py`
- `backend/src/app.py`

**Luồng mới**

```text
Input
  → deterministic safety pre-check
      → urgent: trả ngay
      → medical_caution: giới hạn route + thêm guardrail
      → low: tiếp tục supervisor
```

**Yêu cầu**

- `urgent` không gọi:
  - normalize LLM;
  - supervisor LLM;
  - query rewrite;
  - Qdrant;
  - reranker;
  - response composer.
- Response cấp cứu là template đã duyệt, tiếng Việt có dấu.
- Không đưa ra chẩn đoán.
- Thêm số điện thoại cấp cứu chỉ khi xác định được quốc gia bằng cơ chế đáng tin cậy; không hard-code phỏng đoán.

**Nghiệm thu**

- 20/20 ca urgent trả đúng hành động.
- P95 dưới 500 ms.
- Mock xác nhận số lần gọi LLM và search bằng 0.

### HOT-04 — Tool fast-path

**File chính**

- `backend/src/agents/graph.py`
- `backend/src/health_tools.py`

**Thay đổi**

- Nếu câu hỏi chỉ yêu cầu BMI/PBF/visceral fat và đủ dữ liệu:
  - chạy tool;
  - render bằng template;
  - không rewrite/RAG;
  - composer là tùy chọn, không phải dependency.
- Nếu thiếu dữ liệu, hỏi đúng trường còn thiếu.

**Nghiệm thu**

- BMI end-to-end P95 dưới 500 ms.
- Kết quả số không thay đổi qua nhiều lần gọi.
- Câu trả lời có dấu và giải thích giới hạn của chỉ số.

### HOT-05 — Chuẩn hóa routing

**File chính**

- `backend/src/agents/graph.py`
- `backend/src/agents/parsing.py`
- `backend/src/brain.py`

**Thay đổi**

- Tạo hàm normalize:
  - lowercase;
  - chuẩn hóa Unicode;
  - thêm bản không dấu để match;
  - chuẩn hóa khoảng trắng/đơn vị.
- Thay keyword `"nên"` bằng intent cụ thể.
- Tách `primary_intent` và `secondary_intents`.
- Safety không biểu diễn bằng việc chọn nhầm `InBodyAgent`.
- LLM router chỉ dùng khi deterministic router không đủ confidence.

**Schema đề xuất**

```json
{
  "primary_intent": "training",
  "secondary_intents": ["rag"],
  "confidence": 0.91,
  "reason": "matched training-plan pattern"
}
```

**Nghiệm thu**

- Router accuracy tối thiểu 95% trên ít nhất 100 câu.
- Bộ test gồm câu có dấu, không dấu, typo và cách nói tự nhiên.

### HOT-06 — Response contract và lỗi API

**File chính**

- `backend/src/app.py`
- `backend/src/agents/graph.py`
- `frontend/chat_interface_new.py`

**Response chuẩn**

```json
{
  "request_id": "...",
  "answer": "...",
  "status": "ok|degraded|error",
  "selected_agents": [],
  "agent_trace": [],
  "citations": [],
  "errors": [],
  "latency_ms": 0
}
```

**Thay đổi**

- Validation domain trả HTTP 4xx.
- Lỗi dependency trả 502/503.
- Timeout trả 504 hoặc response degraded có chủ đích.
- Không trả 200 với payload chứa `error` cho input sai.

**Nghiệm thu**

- Contract test giữa frontend/backend đạt.
- UI không phải suy luận lỗi dựa trên chuỗi.

---

## 7. Giai đoạn 2 — dữ liệu và Qdrant v2

### DATA-01 — Hoàn tất import hiện tại nhưng không dùng làm release tự động

**Thực hiện**

- Theo dõi point count tới khi job kết thúc.
- Đọc exit code và import summary.
- So sánh:
  - processed documents;
  - skipped documents;
  - total chunks;
  - error count;
  - Qdrant point count.
- Không coi `collection status=green` là import thành công.

**Nghiệm thu**

- Có import manifest cuối cùng.
- Chênh lệch giữa manifest và Qdrant bằng 0 hoặc được giải thích bằng duplicate policy.

### DATA-02 — Chuẩn hóa schema tài liệu

**File chính**

- `backend/src/import_data.py`
- `backend/src/splitter.py`
- `backend/src/vectorize.py`

**Payload bắt buộc**

```json
{
  "document_id": "stable-id",
  "chunk_id": "stable-id#0001",
  "corpus_version": "2026-07-30-v2",
  "content_type": "inbody_metric|nutrition|exercise|medical_safety|general_health",
  "source": "...",
  "source_url": null,
  "title": "...",
  "language": "vi",
  "content_hash": "...",
  "chunk_index": 1,
  "created_at": "...",
  "text": "..."
}
```

**Quy tắc**

- Không tồn tại đồng thời `general` và `general_health`.
- ID ổn định để import lại không sinh duplicate.
- Hash nội dung dùng để deduplicate.
- Tài liệu safety có provenance rõ ràng.
- Chuỗi hiển thị cho người dùng dùng tiếng Việt có dấu.

**Nghiệm thu**

- 100% point hợp schema.
- Không có content type ngoài enum.
- Duplicate rate dưới 1%, hoặc có lý do rõ.

### DATA-03 — Audit chất lượng corpus

**Kiểm tra**

- Dữ liệu rỗng/quá ngắn.
- Encoding lỗi.
- Recipe bị gắn nhãn sai.
- Tài liệu cùng nội dung nhưng tiêu đề khác.
- Nội dung mâu thuẫn.
- Nguồn thiếu hoặc không đáng tin.
- Nội dung safety quá ít.
- Chunk mất ngữ cảnh hoặc quá dài.

**Đầu ra**

```text
artifacts/data-audit/
  invalid_rows.csv
  duplicates.csv
  distribution.json
  sources.csv
  safety_coverage.md
```

**Nghiệm thu**

- Mỗi content type có owner/nguồn.
- Safety corpus được duyệt riêng.
- Không dùng số lượng lớn nutrition để che lấp thiếu coverage miền khác.

### DATA-04 — Import blue/green

**Thiết kế**

```text
nmk_chatbot_collection_v1  ← đang phục vụ
nmk_chatbot_collection_v2  ← import + validate
alias nmk_chatbot_collection → v1/v2
```

**Quy trình**

1. Tạo v2 với vector size/distance đúng.
2. Import idempotent theo batch.
3. Validate manifest và sample search.
4. Chạy eval.
5. Chuyển alias sang v2.
6. Giữ v1 trong thời gian rollback.

**Nghiệm thu**

- Không downtime khi chuyển collection.
- Rollback alias dưới 5 phút.
- Không xóa v1 trước khi v2 qua quality gate.

### DATA-05 — Payload index và optimizer

**Thực hiện**

- Tạo payload index cho:
  - `content_type`;
  - `source`;
  - `corpus_version`;
  - `document_id`.
- Kiểm tra HNSW indexing threshold và optimizer sau import.
- Đo lại `indexed_vectors_count`.

**Nghiệm thu**

- Filter query không scan payload toàn collection.
- Search P95 không tăng quá ngưỡng khi corpus hoàn tất.

---

## 8. Giai đoạn 3 — hybrid retrieval và chất lượng RAG

### RAG-01 — Thay BM25 global RAM

**Vấn đề hiện tại**

- `_documents`, `_bm25_index`, `_search_engine_initialized` nằm trong process.
- Hai Uvicorn worker có state khác nhau.
- Restart làm mất index.
- Import batch có thể thay index trước đó.

**Phương án khuyến nghị**

Ưu tiên Qdrant dense + sparse hybrid trong cùng collection. Nếu chưa triển khai sparse ngay, dùng một search service/index dùng chung và bền vững; không giữ BM25 độc lập trong từng worker.

**Nghiệm thu**

- Health readiness chứng minh dense và sparse đều sẵn sàng.
- Hai worker trả cùng kết quả.
- Restart backend không làm mất sparse index.

### RAG-02 — Intent-aware retrieval

**Luồng đề xuất**

```text
normalized query
  → intent/content-type candidates
  → original query dense+sparse
  → optional second query only if confidence thấp
  → safety/content filters
  → rerank có điều kiện
  → top-k + citation metadata
```

**Quy tắc quan trọng**

- Medical safety query:
  - ưu tiên/require `medical_safety`;
  - loại recipe/general food candidate;
  - không cho document khác lấn top result nếu safety corpus có hit phù hợp.
- Tool-only query không cần RAG.
- Không mặc định rewrite thành ba query cho mọi câu.

**Nghiệm thu**

- Safety Hit@5 = 100% trên tập safety.
- Không recipe nào xuất hiện trong top 5 safety query.
- Số vector search trung bình mỗi request ≤ 1,5.

### RAG-03 — Gating reranker

**Thay đổi**

- Không bật heuristic reranker mặc định cho mọi domain.
- Log thứ tự trước/sau rerank.
- Chỉ chấp nhận reranker nếu cải thiện MRR/NDCG trên eval set.
- Thêm hard filter trước rerank.

**Nghiệm thu**

- Rerank cải thiện MRR ít nhất 5% hoặc bị tắt.
- Không làm giảm safety recall.

### RAG-04 — Citation và grounded response

**Thay đổi**

- Mỗi chunk trả:
  - document ID;
  - title;
  - source;
  - score;
  - corpus version.
- Composer chỉ được dùng context có score đạt threshold.
- Nếu không đủ context, nói rõ “chưa đủ dữ liệu”.
- Output validator kiểm tra citation tồn tại trong retrieved docs.

**Nghiệm thu**

- Citation precision ≥ 95%.
- Không trích nguồn không có trong context.
- Answer không khẳng định vượt quá nguồn/tool.

### RAG-05 — Bộ benchmark

**Cấu trúc đề xuất**

```text
backend/evals/
  retrieval_cases.jsonl
  routing_cases.jsonl
  safety_cases.jsonl
  answer_cases.jsonl
  run_eval.py
  README.md
```

**Mỗi case retrieval**

```json
{
  "id": "safety-001",
  "query": "Tôi đau ngực và khó thở khi tập",
  "expected_content_types": ["medical_safety"],
  "relevant_document_ids": ["..."],
  "must_not_sources": ["foodrecordfinal_foods"]
}
```

**Quy mô tối thiểu**

| Nhóm | Số case |
|---|---:|
| InBody | 25 |
| Nutrition | 20 |
| Exercise | 20 |
| Safety | 20 |
| Follow-up/personalization | 10 |
| Không dấu/typo/adversarial | 15 |
| **Tổng** | **110** |

**Chỉ số**

- Router accuracy/exact match.
- Recall@5, Precision@5, MRR, NDCG@5.
- Strict top-1 relevance.
- Citation precision.
- Tool numerical correctness.
- Safety pass rate.
- Latency P50/P95/P99.

---

## 9. Giai đoạn 4 — GPU, hiệu năng và UI

### PERF-01 — Quyết định phân bổ RTX 3050 4 GB

**Sự thật cần tính đến**

- Qwen3 8B hiện chiếm khoảng 2,31 GB VRAM nhưng còn có CPU/offload/runtime overhead.
- BGE-M3 FP16 cần thêm VRAM đáng kể.
- Chạy cả hai cùng lúc trên 4 GB có nguy cơ OOM hoặc giảm tốc do trao đổi CPU/GPU.

**Ba cấu hình phải benchmark**

| Cấu hình | LLM | Embedding | Khi dùng |
|---|---|---|---|
| A | Qwen3 8B GPU/partial offload | BGE-M3 CPU | Online hiện tại, ít rủi ro OOM |
| B | Unload/tắt Ollama | BGE-M3 FP16 GPU | Bulk import |
| C | LLM nhỏ/quantized hơn | BGE-M3 GPU | Online nếu chất lượng đạt |

Không quyết định bằng cảm giác. Chạy cùng một benchmark và đo:

- VRAM peak;
- RAM;
- tokens/second;
- embedding docs/second;
- search P95;
- Agent P95;
- OOM/restart count.

**Khuyến nghị ban đầu**

- Khi bulk import: tạm dừng Ollama, dành GPU cho BGE-M3.
- Khi online: bắt đầu với Qwen3 8B + embedding CPU; chỉ chuyển cả hai lên GPU nếu benchmark chứng minh ổn định.

**Nghiệm thu**

- VRAM peak có ít nhất 10% headroom.
- Chạy soak test 2 giờ không OOM/restart.

### PERF-02 — Embedding batching và cache

**File chính**

- `embed_serving/scripts/serve_model.py`
- `backend/src/import_data.py`
- `backend/src/custom_embedding.py`

**Thực hiện**

- Xác nhận runtime thực sự báo `device=cuda`, không chỉ có GPU reservation.
- Xác nhận PyTorch image có CUDA.
- FP16 chỉ bật khi CUDA; CPU giữ FP32.
- Batch import điều chỉnh từ 2 → 4 → 8 theo benchmark VRAM.
- Cache embedding cho query lặp lại có TTL và version model.

**Nghiệm thu**

- Health endpoint báo device, dtype, batch size và model revision.
- Không OOM trên batch đã chọn.
- Import throughput tăng có số liệu trước/sau.

### PERF-03 — Cache và giảm số lần gọi

**Thực hiện**

- Cache deterministic tool result theo input chuẩn hóa.
- Cache query embedding.
- Cache retrieval ngắn hạn theo corpus version.
- Không cache response chứa dữ liệu user nếu key không có user isolation.
- Loại LLM call không cần thiết.

**Nghiệm thu**

- Cache hit không làm trả dữ liệu chéo user.
- P95 giảm nhưng correctness không giảm.

### UI-01 — Trạng thái và timeout

**File chính**

- `frontend/chat_interface_new.py`

**Thực hiện**

- Frontend timeout lớn hơn backend hard timeout 5–10 giây.
- Hiển thị request ID.
- Phân biệt:
  - backend offline;
  - LLM unavailable;
  - data not ready;
  - timeout;
  - degraded fallback.
- Hiển thị tiến độ theo node hoặc streaming nếu backend hỗ trợ.

**Nghiệm thu**

- Không spinner im lặng quá 5 giây.
- User nhận thông báo dễ hiểu, không lộ stack trace.

### UI-02 — Nội dung và cấu trúc production

**Thực hiện**

- Tất cả output tiếng Việt có dấu.
- Bỏ cụm “Multi-Agent RAG MVP” khỏi fallback user-facing.
- Dev tools/System chỉ bật khi `APP_ENV=development`.
- Hiển thị citation rõ ràng.
- Hiển thị trạng thái corpus ready/not ready.
- Không dùng health score như chẩn đoán.

### UI-03 — HTML safety và accessibility

**Thực hiện**

- Escape title/source/content trước khi render.
- Giảm `unsafe_allow_html=True`.
- Nếu buộc dùng HTML, dùng allowlist sanitizer.
- Kiểm thử:
  - `<script>`;
  - event handler;
  - malformed HTML;
  - URL lạ;
  - tiêu đề cực dài.
- Chạy keyboard, focus, contrast, mobile viewport.

**Nghiệm thu**

- Không có HTML injection từ Qdrant payload.
- Không lỗi accessibility nghiêm trọng.
- Layout hoạt động ở 360 px, tablet và desktop.

---

## 10. Giai đoạn 5 — bảo mật và observability

### SEC-01 — Auth và phân quyền

**Thực hiện**

- Bắt buộc xác thực cho profile, InBody measurement và chat history.
- `user_id` lấy từ token/session, không tin trực tiếp giá trị client gửi.
- Endpoint import/create/delete collection chỉ dành cho admin/service account.
- Tách route dev/admin khỏi public API.

**Nghiệm thu**

- User A không đọc/ghi được dữ liệu User B.
- Request không token nhận 401.
- User thường gọi ingest/admin nhận 403.

### SEC-02 — Network và secret

**Thực hiện**

- Không expose Postgres, Valkey, Qdrant ra host ở production nếu không cần.
- Không hard-code password trong Compose.
- Dùng secret manager hoặc file secret ngoài Git.
- TLS ở reverse proxy.
- CORS allowlist và CSRF/XSRF phù hợp.
- Rate limit cho chat/search/import.

### SEC-03 — Dữ liệu sức khỏe

**Thực hiện**

- Xác định dữ liệu nào là nhạy cảm.
- Mã hóa in transit/at rest theo môi trường.
- Audit log truy cập/sửa/xóa.
- Chính sách retention và xóa theo user.
- Không ghi câu hỏi hoặc chỉ số đầy đủ vào log nếu không cần.
- Mask PII trong trace.

### OBS-01 — Logging và metrics

**Mỗi request cần**

- request ID;
- user ID đã hash/mask;
- selected agents;
- latency từng node;
- số LLM calls;
- số input/output tokens;
- số search calls;
- retrieved document IDs/scores;
- fallback/degraded reason;
- corpus/model version.

**Metric**

```text
agent_request_duration_seconds
agent_node_duration_seconds
llm_request_duration_seconds
llm_timeout_total
retrieval_duration_seconds
retrieval_empty_total
safety_urgent_total
fallback_total
qdrant_points_count
embedding_queue_depth
```

**Nghiệm thu**

- Có thể trả lời “request chậm ở node nào?” mà không cần đọc toàn bộ log thủ công.
- Có alert cho LLM timeout, Qdrant unavailable, import mismatch và error-rate.

### OBS-02 — Health đúng nghĩa

Tách:

- `/health/live`: process còn sống.
- `/health/ready`: LLM, embedding, Qdrant, database, corpus manifest sẵn sàng.

Không trả `healthy` nếu BM25/hybrid được cấu hình bắt buộc nhưng chưa initialized, hoặc corpus chưa đạt version yêu cầu.

---

## 11. Giai đoạn 6 — release candidate

### RC-01 — Test pyramid

| Loại test | Nội dung |
|---|---|
| Unit | parsing, routing, tools, safety, scoring, validation |
| Contract | frontend/backend response schema |
| Integration | Ollama, embedding, Qdrant, Postgres, Valkey |
| End-to-end | chat, tool, RAG, safety, personalization |
| Evaluation | retrieval, groundedness, citation, safety |
| Security | authz, injection, rate limit, cross-user access |
| Performance | latency, concurrency, soak, GPU/RAM |
| Visual/accessibility | desktop/mobile, keyboard, contrast |

### RC-02 — Load test

Chỉ chạy sau khi correctness đạt.

**Kịch bản ban đầu**

- 1 user tuần tự để lấy baseline.
- 5 user đồng thời trong 10 phút.
- 10 user đồng thời trong 10 phút.
- Soak 2 giờ với tải thấp.
- Tách tool-only, search-only và full Agent.

**Theo dõi**

- P50/P95/P99.
- Error/timeout rate.
- CPU/RAM/VRAM.
- Qdrant latency.
- queue depth.
- container restart.

### RC-03 — Release checklist

- [ ] Import manifest khớp Qdrant.
- [ ] Corpus version cố định.
- [ ] P0/P1 đã đóng.
- [ ] Unit/integration/eval test đạt.
- [ ] Safety 100%.
- [ ] Router ≥ 95%.
- [ ] Retrieval đạt KPI.
- [ ] Latency đạt KPI.
- [ ] Auth/authz đạt.
- [ ] HTML injection test đạt.
- [ ] Backup và rollback đã diễn tập.
- [ ] Monitoring/alert hoạt động.
- [ ] Người phụ trách duyệt nội dung safety.

---

## 12. KPI và quality gate

### Gate A — Agent usable

| KPI | Ngưỡng |
|---|---:|
| Urgent safety P95 | < 500 ms |
| BMI/tool-only P95 | < 500 ms |
| General chat hoàn tất P95 | < 15 giây |
| RAG chat hoàn tất P95 | < 20 giây |
| Request > 60 giây | 0 |
| LLM route rỗng | 0 |

### Gate B — RAG beta

| KPI | Ngưỡng |
|---|---:|
| Router accuracy | ≥ 95% |
| Recall@5 | ≥ 90% |
| MRR | ≥ 0,80 |
| Strict top-1 relevance | ≥ 75% |
| Safety Hit@5 | 100% |
| Recipe trong safety top 5 | 0 |
| Citation precision | ≥ 95% |

### Gate C — Production candidate

| KPI | Ngưỡng |
|---|---:|
| Error rate ở tải mục tiêu | < 1% |
| Timeout rate | < 0,5% |
| Soak test | 2 giờ không restart/OOM |
| Cross-user data leak | 0 |
| P0/P1 security | 0 |
| Visual/accessibility nghiêm trọng | 0 |

Các ngưỡng có thể điều chỉnh sau baseline ổn định, nhưng không được hạ riêng để “cho pass”.

---

## 13. Chiến lược rollback

### Code

- Mỗi giai đoạn là commit/PR riêng.
- Feature flag cho:
  - Qwen thinking;
  - query rewrite;
  - reranker;
  - sparse hybrid;
  - streaming;
  - new router.
- Không gộp hotfix safety với migration dữ liệu lớn.

### Qdrant

- Dùng collection version + alias.
- Giữ collection cũ read-only trong thời gian quan sát.
- Rollback bằng chuyển alias, không import ngược.

### Model

- Ghi model name, digest, quantization và config trong mỗi release.
- Có thể quay về model/config trước mà không đổi API contract.

### UI

- Frontend phải tương thích với response `status=degraded`.
- Nếu streaming lỗi, fallback về response đồng bộ trong giới hạn backend.

---

## 14. Phân công đề xuất

Nếu có nhiều người:

| Vai trò | Trách nhiệm |
|---|---|
| Backend/Agent | HOT-01 đến HOT-06, response contract |
| Data/RAG | DATA-01 đến RAG-05 |
| Frontend | UI-01 đến UI-03 |
| Platform/Security | PERF, SEC, OBS, deploy/rollback |
| Domain reviewer | Safety corpus, template và acceptance cases |

Nếu làm một mình, thứ tự bắt buộc:

1. BL;
2. HOT;
3. DATA;
4. RAG;
5. PERF/UI;
6. SEC/OBS;
7. RC.

---

## 15. Việc nên làm ngay trong 24 giờ đầu

1. Không restart embedding service nếu import hiện tại chưa kết thúc hoặc chưa chủ động dừng.
2. Theo dõi job import và lưu summary cuối.
3. Viết test tái hiện router rỗng, BMI timeout và urgent timeout.
4. Cấu hình `OLLAMA_THINK=false` cho runtime Qwen3 hiện tại; code giữ model-agnostic.
5. Thêm safety fast-path.
6. Thêm tool fast-path cho BMI.
7. Đo lại ba ca:
   - lời chào;
   - BMI;
   - đau ngực + khó thở.
8. Chỉ khi ba ca đạt mới chuyển sang làm lại Qdrant/RAG.

**Mục tiêu sau 24 giờ:**

- lời chào dưới 15 giây;
- BMI dưới 500 ms;
- urgent dưới 500 ms;
- không còn route rỗng;
- không request nào vượt 30 giây.

---

## 16. Thứ tự triển khai kỹ thuật đề xuất

```text
1. Regression tests
2. Model capability config + task-specific LLM budgets
3. Safety fast-path
4. Tool fast-path
5. Router normalization
6. Response/error contract
7. Finish and audit import
8. Build Qdrant collection v2
9. Persistent dense+sparse hybrid
10. Intent filters + reranker gate
11. RAG benchmark
12. GPU configuration benchmark
13. UI timeout/streaming/sanitization
14. Auth + data isolation
15. Observability + load/soak test
16. Beta release gate
```

Đây là thứ tự theo rủi ro và phụ thuộc. Việc làm UI đẹp hoặc tăng batch embedding trước khi sửa safety/timeout sẽ không cải thiện chất lượng hệ thống theo cách có thể nghiệm thu.

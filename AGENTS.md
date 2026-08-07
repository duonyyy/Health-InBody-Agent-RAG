# AGENTS.md

Hướng dẫn làm việc cho coding agent trong dự án Health/InBody Agent RAG.

## 1. Mục tiêu dự án

Dự án cung cấp trợ lý tiếng Việt về:

- chỉ số InBody như BMI, PBF, SMM, BFM và mỡ nội tạng;
- dinh dưỡng và lịch tập ở mức tham khảo;
- RAG trên corpus sức khỏe/InBody;
- cảnh báo an toàn y tế, không chẩn đoán và không kê đơn.

Hệ thống hiện là MVP đang được nâng lên Agent RAG beta. Không được mô tả hệ thống là production-ready nếu chưa qua các quality gate trong `KE_HOACH_CAI_THIEN_HE_THONG_AGENT_RAG.md`.

## 2. Giao tiếp và tư duy

- Trao đổi với người dùng bằng tiếng Việt, ngắn gọn và thẳng thắn.
- Chủ động chỉ ra giả định sai, dữ liệu thiếu, thiên kiến corpus và rủi ro an toàn.
- Không biến kết quả smoke test nhỏ thành tuyên bố accuracy tổng quát.
- Phân biệt rõ:
  - source đã sửa;
  - test trong process;
  - container đã restart;
  - runtime thật đã nhận code mới.
- Khi công việc kéo dài, cập nhật tiến độ theo từng đợt và nêu blocker thật.

## 3. Kiến trúc chính

| Thành phần | Vị trí | Vai trò |
|---|---|---|
| Backend | `backend/src/` | FastAPI, LangGraph Agent, tools, retrieval |
| Agent graph | `backend/src/agents/graph.py` | Routing và orchestration |
| LLM adapter | `backend/src/brain.py` | Ollama/OpenAI/custom provider |
| Retrieval | `backend/src/search.py` | Dense/BM25/hybrid search |
| Qdrant | `backend/src/vectorize.py` | Vector collection và search |
| Import | `backend/src/import_data.py` | Validate, chunk, embed, upsert |
| Embedding | `embed_serving/` | BGE-M3 serving |
| Frontend | `frontend/chat_interface_new.py` | Streamlit UI |
| Database | `database/`, `backend/src/database.py` | PostgreSQL/personalization |
| Cache/queue | Valkey + Celery | Cache và task bất đồng bộ |

Các tài liệu bắt buộc đọc trước thay đổi lớn:

1. `KE_HOACH_CAI_THIEN_HE_THONG_AGENT_RAG.md`
2. `BAO_CAO_KIEM_THU_HE_THONG_2026-07-30.md`
3. `SETUP.md`
4. README của component đang sửa.

## 4. Quy tắc không được vi phạm

### 4.1 Model-agnostic

- Không hard-code tên model trong `backend/src`.
- Provider, model và capability phải lấy từ biến môi trường.
- Các biến hiện dùng:
  - `LLM_PROVIDER`;
  - `OLLAMA_MODEL`;
  - `OPENAI_MODEL`;
  - `OLLAMA_THINK=auto|true|false`;
  - task token/timeout variables.
- `auto` phải bỏ field model-specific khỏi request thay vì đoán model hỗ trợ.
- Không viết điều kiện kiểu `if model == "qwen..."`.
- Khi đổi model, API contract và Agent graph không được buộc phải đổi.

### 4.2 Safety trước LLM/RAG

- Deterministic safety pre-check luôn chạy trước route, query rewrite và retrieval.
- `urgent` phải trả fast-path; không gọi LLM, Qdrant, reranker hoặc web search.
- Không chẩn đoán, kê đơn hoặc cam kết kết quả y khoa.
- Không để câu trả lời do LLM sinh làm mất cảnh báo từ safety tool.
- Mọi thay đổi safety phải có regression test.

### 4.3 Dữ liệu sức khỏe

- Không log PII/chỉ số sức khỏe đầy đủ nếu không cần.
- Không tin `user_id` do client gửi trong môi trường production; phải lấy từ auth context.
- Không làm lộ dữ liệu giữa hai user.
- Không đưa secret, password hoặc API key vào Git, report hay log.

### 4.4 Qdrant và import

- Không restart embedding/backend khi bulk import đang chạy nếu chưa kiểm tra và chủ động chấp nhận dừng job.
- Trước mọi restart, ghi lại:
  - point count;
  - import process/job status;
  - collection status;
  - manifest hoặc log cuối.
- Không xóa/ghi đè collection đang phục vụ.
- Migration phải dùng collection version mới và alias blue/green.
- Import phải idempotent, dùng stable ID/content hash và có manifest.
- `green` chỉ chứng minh collection hoạt động, không chứng minh import đầy đủ.
- Không so sánh retrieval benchmark khi corpus version khác nhau.

### 4.5 GPU 4 GB

- Không giả định Qwen 8B và BGE-M3 FP16 luôn chạy đồng thời vừa VRAM.
- Bulk import: ưu tiên benchmark phương án unload LLM và dành GPU cho embedding.
- Online: benchmark ít nhất cấu hình LLM GPU + embedding CPU trước khi bật cả hai trên GPU.
- Chỉ bật FP16 khi runtime thật báo CUDA.
- Luôn ghi device, dtype, batch size, VRAM peak và throughput.

## 5. Quy trình triển khai

Chia thay đổi thành các đợt nhỏ:

1. Viết regression test tái hiện lỗi.
2. Sửa source nhỏ nhất giải quyết nguyên nhân gốc.
3. Chạy unit test.
4. Chạy integration test không phá dữ liệu.
5. Kiểm tra diff và các thay đổi sẵn có.
6. Kiểm tra job import/runtime trước restart.
7. Deploy có kiểm soát.
8. Test lại qua HTTP thật.
9. Cập nhật phần “Tiến độ triển khai” trong kế hoạch.

Không triển khai đồng thời hotfix Agent và migration Qdrant lớn trong cùng một bước.

## 6. Quy tắc sửa file và Git

- Giữ nguyên thay đổi có sẵn của người dùng.
- Luôn kiểm tra `git status --short` và diff của file trước khi sửa.
- Không dùng `git reset --hard`, `git checkout --` hoặc xóa thay đổi chưa xác định chủ sở hữu.
- Dùng patch nhỏ, dễ review.
- Không commit/stage/push nếu người dùng chưa yêu cầu.
- File tạm/test artifact phải được dọn sau khi dùng.
- Không chỉnh file ngoài workspace.

Nếu repo có `.codegraph/`, dùng CodeGraph trước grep/read để hiểu call path. Nếu không có, dùng `rg`/`rg --files`; không tự tạo index.

## 7. Chuẩn code

### Python

- Code chạy trên Python của backend image; tránh dùng tính năng vượt version runtime.
- Type hint cho public/internal boundary quan trọng.
- Không bắt `Exception` rồi im lặng; phải log hoặc trả degraded reason.
- Không dùng `time.sleep()` trong `async def`; dùng `asyncio.sleep()` hoặc chuyển polling ra worker.
- Không đặt state bền vững trong global RAM nếu chạy nhiều Uvicorn worker.
- Tách deterministic logic khỏi LLM để unit test không cần network.

### API

- Input sai: HTTP 4xx.
- Dependency lỗi: 502/503.
- Timeout: 504 hoặc response `degraded` có chủ đích.
- Không trả HTTP 200 với payload chỉ chứa trường `error`.
- Response Agent nên giữ contract:

```json
{
  "answer": "...",
  "status": "ok|degraded|error",
  "fast_path": null,
  "selected_agents": [],
  "agent_trace": [],
  "tool_results": [],
  "safety_result": {},
  "errors": [],
  "latency_ms": 0
}
```

### UI

- Nội dung user-facing phải là tiếng Việt có dấu.
- Không hiển thị stack trace hoặc thuật ngữ nội bộ như “MVP fallback”.
- Escape title/source/content từ Qdrant trước khi render.
- Hạn chế `unsafe_allow_html=True`.
- Dev tools/System phải ẩn ở production.
- Frontend timeout phải lớn hơn backend hard timeout.

## 8. Retrieval và RAG

- Tool-only query không được gọi RAG nếu tool đã đủ trả lời.
- Query gốc là retrieval query đầu tiên.
- Không mặc định tạo ba query cho mọi request.
- Medical safety query phải filter/boost `medical_safety` và loại recipe.
- Reranker chỉ bật khi chứng minh cải thiện MRR/NDCG trên eval set.
- Citation phải trỏ tới document thật trong retrieved context.
- Nếu context yếu hoặc không có, nói rõ thiếu dữ liệu.
- Không gọi hệ thống là “hybrid” nếu sparse/BM25 chưa thực sự tham gia.
- Không giữ BM25 riêng trong RAM của từng worker.

## 9. Test bắt buộc

### Unit test nhanh

PowerShell:

```powershell
$env:PYTHONPATH=(Resolve-Path 'backend/src').Path
python -m pytest backend/tests/unit -q -p no:cacheprovider
```

Các fast-path phải mock LLM/retrieval thành hàm gây lỗi để chứng minh chúng không bị gọi.

### Syntax

```powershell
python -m py_compile backend/src/brain.py backend/src/agents/graph.py backend/src/app.py
```

### Compose validation

```powershell
docker compose -f backend/docker-compose.yml config
docker compose -f embed_serving/docker-compose.serving.yml config
docker compose -f frontend/docker-compose.yml config
```

### Runtime smoke test

Sau deploy, kiểm tra tối thiểu:

1. `GET /health`
2. lời chào;
3. BMI 72 kg/170 cm;
4. đau ngực + khó thở;
5. query InBody;
6. query nutrition;
7. query exercise;
8. query safety retrieval;
9. input âm trả 422.

Không dùng kết quả TestClient trong process thay cho test HTTP runtime.

## 10. Quality gate

### Agent P0

- Urgent safety P95 < 500 ms.
- BMI/tool-only P95 < 500 ms.
- Không LLM/search call ở fast-path.
- Không route rỗng.
- Không request chuẩn vượt 60 giây.

### RAG beta

- Router accuracy ≥ 95%.
- Recall@5 ≥ 90%.
- Strict top-1 relevance ≥ 75%.
- Safety Hit@5 = 100%.
- Recipe trong safety top 5 = 0.
- Citation precision ≥ 95%.

### Production candidate

- Không còn P0/P1.
- Không cross-user data leak.
- Auth/authz và rate limit hoạt động.
- Soak test không OOM/restart.
- Visual/accessibility không có lỗi nghiêm trọng.

## 11. Definition of Done

Một task chỉ hoàn thành khi:

- source đã sửa;
- test liên quan đã thêm và đạt;
- không làm hỏng test cũ;
- diff không có lỗi whitespace/syntax;
- runtime đã được deploy nếu task yêu cầu;
- HTTP smoke test sau deploy đạt;
- số liệu trước/sau được ghi lại;
- tài liệu tiến độ được cập nhật;
- blocker hoặc phần chưa test được nói rõ.

Nếu mới sửa source nhưng chưa restart container, trạng thái phải ghi là **source-ready, chưa deploy**, không được ghi “đã sửa hệ thống đang chạy”.


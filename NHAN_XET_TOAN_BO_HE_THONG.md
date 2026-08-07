# NHẬN XÉT TOÀN BỘ HỆ THỐNG HEALTH/INBODY MULTI-AGENT RAG

**Ngày đánh giá:** 30/07/2026  
**Phạm vi:** toàn bộ repository tại thời điểm đánh giá, gồm backend, frontend, embedding service, data pipeline, database, Docker Compose và tài liệu dự án.

## 1. Kết luận điều hành

Hệ thống hiện là một **MVP có thể dùng để trình diễn ý tưởng**, nhưng **chưa đủ điều kiện triển khai cho người dùng thật**, đặc biệt vì đây là sản phẩm xử lý dữ liệu sức khỏe.

Điểm mạnh chính là cấu trúc thành phần tương đối rõ, có luồng agent, health tools có tính xác định, cơ chế fallback khi thiếu LLM/RAG và tài liệu dự án khá đầy đủ. Tuy nhiên, giá trị cốt lõi của đề tài vẫn chưa được chứng minh bằng kiểm thử hoặc benchmark: chưa có OCR InBody, chưa có tập đánh giá retrieval/answer, chưa có xác thực người dùng, chưa có bảo vệ dữ liệu sức khỏe và hybrid search hiện có lỗi kiến trúc làm BM25 không ổn định.

Đánh giá theo mục đích sử dụng:

| Mục đích | Mức sẵn sàng | Nhận xét |
| --- | --- | --- |
| Demo nội bộ có người hướng dẫn | **Khá** | Có thể trình diễn chat, agent trace và health tools nếu các service được cấu hình đúng. |
| Bảo vệ đồ án | **Trung bình khá** | Kiến trúc đủ để trình bày, nhưng cần benchmark và sửa các lỗi RAG chính để kết quả có sức thuyết phục. |
| Pilot với người dùng giới hạn | **Thấp** | Thiếu authentication, privacy control, audit, test và giám sát chất lượng y tế. |
| Production công khai | **Chưa sẵn sàng** | Có rủi ro truy cập trái phép dữ liệu sức khỏe, poisoning RAG, sai lệch tư vấn và vận hành không ổn định. |

### Các vấn đề cần xử lý trước tiên

1. Thêm xác thực, phân quyền và tách dữ liệu theo người dùng.
2. Thiết kế lại BM25 để dùng persistent/shared index; hiện mỗi worker giữ một bản RAM khác nhau và mỗi batch ingest ghi đè index trước.
3. Bổ sung guardrail kiểm tra **câu trả lời cuối**, không chỉ kiểm tra câu hỏi đầu vào.
4. Khóa các endpoint quản trị/index dữ liệu và chống prompt injection/RAG poisoning.
5. Tạo bộ test tự động và benchmark RAG/safety trước khi tiếp tục mở rộng tính năng.
6. Làm cho cấu hình embedding có một nguồn duy nhất và thực sự tôn trọng cờ bật/tắt.

## 2. Phạm vi và phương pháp đánh giá

Đã kiểm tra:

- 33 file Python trong backend, frontend, embedding service và data pipeline.
- Request/response API, luồng sync/async, LangGraph state và agent routing.
- PostgreSQL schema, lớp personalization và cách lưu hội thoại.
- BM25, Qdrant, embedding, rerank, query rewriting và ingest.
- Streamlit UI, Dockerfile, Docker Compose, biến môi trường và startup scripts.
- Corpus hiện có, source manifest và các báo cáo build dataset.
- README, SETUP và các tài liệu kỹ thuật trong `docs/`.

Kết quả kiểm tra kỹ thuật:

- Tất cả 33 file Python **parse AST thành công**.
- `backend/docker-compose.yml`, `frontend/docker-compose.yml` và `embed_serving/docker-compose.serving.yml` **hợp lệ về cú pháp Compose**.
- CLI của `build_embedding_dataset.py` và `index_mvp_dataset.py` mở được.
- Repository **không có test tự động**; `unittest discover` trả về `Ran 0 tests`.
- Chưa chạy được smoke test end-to-end vì Docker daemon không hoạt động trong lúc đánh giá.
- Import backend trên Python host thất bại do môi trường host thiếu `psycopg2`; đây chưa đủ bằng chứng kết luận Docker image bị lỗi vì dependency này có trong `backend/requirements.txt`.

Vì chưa chạy được hệ thống đầy đủ, các kết luận về latency, tải đồng thời, chất lượng câu trả lời và độ ổn định container vẫn cần được xác nhận lại bằng runtime test.

## 3. Kiến trúc thực tế

Luồng chat chính:

```text
Streamlit
  -> FastAPI /chat/complete
  -> tải personalization từ PostgreSQL
  -> QuestionNormalizerAgent
  -> SupervisorAgent chọn danh sách agent
  -> lần lượt đi qua mọi node chuyên môn
       InBody -> Nutrition -> Training -> RAG -> Web -> General
     mỗi node tự bỏ qua nếu không được chọn
  -> SafetyAgent
  -> ResponseComposerAgent
  -> trả answer + trace + tool results + retrieved docs + personalization
```

Các lớp lưu trữ và dịch vụ:

```text
PostgreSQL : user profile, InBody measurements, schema chat/document
Valkey     : Celery broker/result và cache có fallback RAM
Qdrant     : dense vector
RAM process: BM25 documents/index
Flask      : BGE-M3 embedding service
LLM        : Ollama, OpenAI hoặc custom endpoint
Tavily     : web search tùy chọn
```

Một sự thật cần nói rõ: graph hiện không phân nhánh hoặc chạy agent song song. Tất cả node được nối tuần tự trong `backend/src/agents/graph.py:579-589`; supervisor chỉ ghi danh sách `selected_agents`, sau đó từng node kiểm tra tên mình có được chọn hay không. Đây vẫn là orchestration nhiều thành phần, nhưng chưa phải multi-agent planner hay graph động như sơ đồ kiến trúc có thể khiến người đọc kỳ vọng.

## 4. Những điểm làm tốt

### 4.1. Tách thành phần tương đối rõ

- Backend, frontend, embedding serving, data pipeline và database được đặt riêng.
- Các health tools, parsing, retrieval, rerank, personalization và agent graph có module độc lập.
- `configs.py` đã gom một số runtime defaults dùng chung cho backend.

### 4.2. Có cơ chế suy giảm chức năng

- LLM lỗi thì agent trả fallback thay vì làm toàn bộ request sập.
- Redis lỗi thì cache chuyển sang RAM.
- Vector search lỗi thì retrieval vẫn có thể dùng BM25.
- LangGraph không import được thì có sequential runner.

Cách làm này hữu ích cho demo, nhưng cần health status rõ ràng để người vận hành biết hệ thống đang chạy ở chế độ suy giảm.

### 4.3. Health tools có tính xác định và dễ kiểm thử

Các phép tính BMI, PBF, mỡ nội tạng, nutrition và training được tách khỏi LLM. Đây là hướng đúng vì kết quả định lượng không nên phụ thuộc hoàn toàn vào model sinh văn bản.

### 4.4. Có personalization schema cơ bản

Database đã mô hình hóa:

- User profile.
- Kết quả đo InBody theo thời gian.
- Chat session/message.
- Document/chunk.
- Uploaded file cho roadmap OCR.

Chỉ mục `inbody_measurements(user_id, measurement_date DESC)` phù hợp với truy vấn lấy lần đo mới nhất.

### 4.5. Tài liệu có thừa nhận một phần giới hạn MVP

README và tài liệu data pipeline đã nói rõ:

- Chưa có upload/OCR thật.
- Corpus chưa phải clinical benchmark.
- Async chat chưa truyền history.
- Supervisor còn dựa nhiều vào keyword.

Đây là điểm tốt về tính trung thực học thuật. Tuy nhiên vẫn còn một số mô tả vượt quá mã thực tế, được nêu ở phần sau.

## 5. Phát hiện theo mức độ ưu tiên

Quy ước:

- **P0 – Critical:** có thể gây lộ dữ liệu, gây hại hoặc làm sai chức năng cốt lõi.
- **P1 – High:** ảnh hưởng lớn đến độ tin cậy, bảo mật hoặc khả năng vận hành.
- **P2 – Medium:** nợ kỹ thuật hoặc thiếu sót đáng kể nhưng có thể tạm chấp nhận cho demo.
- **P3 – Low:** cải thiện chất lượng, tính nhất quán hoặc trải nghiệm phát triển.

### 5.1. P0 – Không có authentication/authorization cho dữ liệu sức khỏe

**Bằng chứng**

- Các endpoint `/users/{user_id}/profile`, `/measurements` và `/personalization-context` không có dependency xác thực: `backend/src/app.py:174-212`.
- Frontend cho phép nhập trực tiếp `User ID`: `frontend/chat_interface_new.py:350-353`.
- Chat response chứa cả `personalization_context`, `tool_results` và `retrieved_docs`: `backend/src/agents/graph.py:681-690`.
- Endpoint lấy kết quả Celery nhận bất kỳ `task_id` nào mà không kiểm tra chủ sở hữu: `backend/src/app.py:254-279`.

**Tác động**

Người dùng chỉ cần đoán hoặc biết `user_id` là có thể đọc/sửa hồ sơ, bệnh nền và kết quả InBody của người khác. Đây là dữ liệu sức khỏe nhạy cảm. Việc dùng `demo-user` làm mặc định còn khiến nhiều người dùng có thể dùng chung một hồ sơ.

**Khuyến nghị**

- Dùng OIDC/OAuth2 hoặc session authentication.
- Lấy `user_id` từ token/session, không tin `user_id` do client gửi.
- Áp dụng object-level authorization cho profile, measurement, chat task và export.
- Tách role `user`, `admin`, `ingestion-worker`.
- Không trả raw personalization/tool/retrieved docs trong API production nếu frontend không cần.
- Ghi audit log cho đọc/sửa/xóa dữ liệu sức khỏe.

### 5.2. P0 – BM25 không bền vững và có thể chỉ chứa batch cuối cùng

**Bằng chứng**

- BM25 và danh sách document là biến global trong RAM: `backend/src/search.py:19-21`.
- `initialize_search_index()` thay toàn bộ `_documents`: `backend/src/search.py:163-192`.
- Mỗi lần `/documents/index` nhận một batch, `index_health_documents()` gọi lại `initialize_search_index(normalized_docs)`: `backend/src/tasks.py:121-153`.
- Script ingest mặc định gửi batch 50: `data_pipeline/utils/index_mvp_dataset.py:79-94`.
- Backend chạy 2 Uvicorn workers: `backend/docker-compose.yml:10`.
- Hàm load BM25 từ Qdrant tồn tại nhưng không được gọi khi startup hoặc trước search: `backend/src/search.py:406-451`.

**Tác động**

Với corpus 5.345 documents và batch 50, Qdrant có thể chứa toàn bộ dữ liệu nhưng BM25 của process xử lý batch cuối chỉ còn khoảng 45 documents. Worker còn lại có thể có index rỗng hoặc một batch khác. `/document/create` thậm chí thay BM25 bằng đúng một document.

Do đó, tên gọi “hybrid search” không đảm bảo đúng trong runtime hiện tại.

**Khuyến nghị**

- Không giữ corpus BM25 làm mutable process-global state.
- Dùng OpenSearch/Elasticsearch/PostgreSQL FTS, hoặc lưu BM25 index dạng artifact được load giống nhau ở mọi worker.
- Nếu vẫn dùng RAM cho MVP: build toàn bộ index một lần, atomic swap, khóa cập nhật và load tại startup.
- Tách endpoint ingest khỏi API chat.
- Sau ingest phải kiểm tra `documents_count == expected_count` trên mọi replica.

### 5.3. P0 – Guardrail y tế chưa kiểm tra câu trả lời cuối

**Bằng chứng**

- `SafetyAgent` chỉ gọi `check_medical_safety(question, conditions)`: `backend/src/agents/graph.py:455-466`.
- Sau đó LLM tự tổng hợp câu trả lời: `backend/src/agents/graph.py:502-550`.
- Không có bước post-generation validation trước khi trả cho người dùng.
- Safety checker chỉ là danh sách keyword ngắn: `backend/src/health_tools.py:275-336`.

**Tác động**

LLM vẫn có thể sinh nội dung chẩn đoán, liều thuốc, lời khuyên cực đoan hoặc bỏ qua cảnh báo. Với tình huống khẩn cấp, hệ thống không ép dùng một response template ưu tiên cấp cứu; lời cảnh báo có thể bị chìm trong phần tư vấn.

**Khuyến nghị**

- Dùng pipeline `input triage -> generation -> output safety validator -> deterministic override`.
- Với `urgent`, bỏ qua câu trả lời tư vấn thông thường và trả template khẩn cấp đã duyệt.
- Thêm rules cho thuốc/liều, tự hại, thai kỳ, trẻ em, rối loạn ăn uống, bệnh thận/gan/tim và chống chỉ định tập luyện.
- Thêm red-team test bằng tiếng Việt có dấu, không dấu, viết tắt, phủ định và câu hỏi gián tiếp.
- Mời chuyên gia y tế duyệt threshold, wording và escalation policy.

### 5.4. P0 – Endpoint ingest mở tạo nguy cơ RAG poisoning và prompt injection

**Bằng chứng**

- `/collection/create`, `/document/create`, `/documents/index` và `/data/import` không có auth: `backend/src/app.py:314-404`.
- Nội dung retrieved document được chèn trực tiếp vào prompt: `backend/src/agents/graph.py:469-527`.
- Web result và user profile cũng được đưa trực tiếp vào prompt mà không có trust boundary.

**Tác động**

Kẻ tấn công có thể index tài liệu chứa chỉ dẫn như “bỏ qua system prompt”, làm sai câu trả lời y tế, chèn nguồn giả hoặc phá collection. Vì ingestion dùng embedding service, endpoint này còn có thể bị lạm dụng để tiêu tốn CPU/RAM.

**Khuyến nghị**

- Chỉ cho service account/admin truy cập endpoint ingest.
- Đưa ingestion ra worker/internal network, không expose công khai.
- Validate kích thước, loại nội dung, metadata và nguồn.
- Gắn trust level cho tài liệu; không để content được diễn giải như instruction.
- Thêm prompt-injection detector, citation verifier và allowlist nguồn y tế.
- Rate limit và quota theo principal.

### 5.5. P1 – Cấu hình embedding mâu thuẫn và cờ disable không có tác dụng

**Bằng chứng**

- `config/settings.yaml` khai báo `multilingual-e5-small`, vector 384.
- Backend, `.env.example` và BGE-M3 dùng vector 1024.
- Không có mã nào đọc `config/settings.yaml`.
- `CUSTOM_EMBEDDING_ENABLED` và `USE_OPENAI_FALLBACK` được đọc tại `backend/src/custom_embedding.py:18-23`, nhưng không được dùng để quyết định luồng.
- `brain.get_embedding()` luôn gọi custom service: `backend/src/brain.py:200-214`.
- `SETUP.md` hướng dẫn đặt `CUSTOM_EMBEDDING_ENABLED=false` để backend không gọi service, nhưng mã hiện tại không thực hiện điều này.

**Tác động**

Người vận hành có thể tưởng vector search đã tắt an toàn nhưng backend vẫn gọi embedding endpoint. Cấu hình 384/1024 dễ tạo lỗi dimension hoặc collection phải tạo lại.

**Khuyến nghị**

- Chọn một hệ cấu hình duy nhất, ưu tiên environment + typed settings.
- Xóa hoặc cập nhật `config/settings.yaml`.
- Nếu embedding disabled, trả `None` rõ ràng và không gọi HTTP.
- Thực hiện fallback đúng theo cờ; kiểm tra dimension từ `/health` trước khi index.
- Fail fast khi `VECTOR_SIZE` khác model dimension.

### 5.6. P1 – Async API làm nghẽn event loop và khác hành vi sync

**Bằng chứng**

- `get_response()` là `async def` nhưng dùng `time.sleep(0.5)` trong vòng lặp tối đa 60 giây: `backend/src/app.py:254-273`.
- Async task không nhận `history`: `backend/src/app.py:250`.
- Worker luôn gọi `multi_agent_handle(..., history=[])`: `backend/src/tasks.py:325-340`.

**Tác động**

Mỗi request poll giữ worker event loop, làm giảm concurrency. Câu hỏi follow-up có thể được hiểu khác nhau giữa sync và async.

**Khuyến nghị**

- Endpoint status chỉ trả trạng thái ngay lập tức; client tự poll.
- Hoặc dùng `await asyncio.sleep`, nhưng không nên giữ HTTP request 60 giây chỉ để poll backend.
- Truyền history/conversation ID vào task.
- Ràng buộc task ownership với authenticated user.

### 5.7. P1 – Dữ liệu đầu vào và health tools chưa được validate đủ

**Bằng chứng**

- Pydantic request chủ yếu dùng `float` không có giới hạn sinh lý: `backend/src/app.py:97-150`.
- PBF 150% vẫn được phân loại thay vì báo lỗi.
- `suggest_training_plan()` nhận goal/fitness level bất kỳ; goal lạ bị xử lý như maintenance và fitness level không làm thay đổi kế hoạch: `backend/src/health_tools.py:223-269`.
- `activity_level` của nutrition chỉ được echo lại, không ảnh hưởng phép tính: `backend/src/health_tools.py:161-217`.
- NutritionAgent dùng cân nặng mặc định 70 kg khi thiếu dữ liệu: `backend/src/agents/graph.py:319-339`.
- TrainingAgent luôn dùng `fitness_level="beginner"`: `backend/src/agents/graph.py:343-363`.

**Tác động**

Hệ thống có thể tạo khuyến nghị “cá nhân hóa” từ dữ liệu mặc định hoặc giá trị vô lý mà không nói đủ rõ. Điều này đặc biệt nguy hiểm khi người dùng tưởng đây là kết quả tính toán chính xác.

**Khuyến nghị**

- Thêm `ge/le`, enum và validator cross-field trong Pydantic.
- Không dùng 70 kg làm mặc định để đưa ra gram protein; yêu cầu thêm dữ liệu.
- Nếu fitness/activity không được dùng, bỏ khỏi contract hoặc triển khai thật.
- Phân biệt `insufficient_data`, `invalid_data` và kết quả hợp lệ.
- Viết unit test cho boundary, đơn vị, dấu phẩy thập phân và câu nhập tiếng Việt.

### 5.8. P1 – Triển khai Docker đang mở nhiều bề mặt tấn công

**Bằng chứng**

- PostgreSQL dùng password hard-code và publish port 5432.
- Valkey không có password và publish port 6379.
- Qdrant publish 6333/6334, không thấy API key/TLS.
- API publish 8000; không có reverse proxy/TLS/auth.
- Streamlit tắt CORS và XSRF protection: `frontend/entrypoint.sh:90-103`.
- Container chạy bằng root; không có `USER`.
- Qdrant dùng tag `latest`.
- Backend bind-mount toàn bộ source vào container: `backend/docker-compose.yml:22-23`.

**Tác động**

Cấu hình phù hợp cho máy dev cô lập, không phù hợp server hoặc mạng dùng chung. Redis/Celery result có thể chứa dữ liệu chat. Qdrant chứa corpus có thể bị sửa trực tiếp.

**Khuyến nghị**

- Chỉ publish frontend/reverse proxy; database, cache, Qdrant ở internal network.
- Dùng secret manager, mật khẩu mạnh, TLS và network policy.
- Bật XSRF; không tắt CORS nếu không có lý do đã kiểm chứng.
- Chạy non-root, pin image version/digest, thêm read-only filesystem khi có thể.
- Bỏ bind mount source trong production.
- Thêm dependency healthcheck và `condition: service_healthy`.

### 5.9. P1 – Không có test tự động, CI hoặc benchmark chất lượng

**Bằng chứng**

- Không có thư mục test Python, `pytest.ini`, `pyproject.toml` test config hay workflow CI.
- `docs/test.md` chỉ chứa câu hỏi demo thủ công.
- `unittest discover` phát hiện 0 test.
- Tài liệu data pipeline thừa nhận chưa có retrieval benchmark.

**Tác động**

Không thể biết thay đổi có làm hỏng parsing, routing, safety, DB, retrieval hay API contract. Các mục tiêu như OCR >85%, citation đúng hoặc RAG tốt chưa có số liệu chứng minh.

**Khuyến nghị**

Tạo ít nhất:

- Unit test: parsing, health tools, safety rules, score fusion, data validation.
- API test: auth, profile isolation, chat sync/async, error mapping.
- Integration test: PostgreSQL, Valkey, Qdrant, embedding dimension.
- RAG benchmark: Recall@k, MRR/nDCG, groundedness, citation precision.
- Safety benchmark: urgent recall, harmful advice rate, refusal correctness.
- Golden conversation tests bằng tiếng Việt.
- CI chạy lint, type check, test, dependency scan và Docker build.

### 5.10. P1 – Corpus lệch mạnh so với bài toán InBody

Theo `embedding_build_report.json`, corpus có:

| Loại | Số document | Tỷ lệ xấp xỉ |
| --- | ---: | ---: |
| Nutrition | 4.918 | 92,0% |
| Exercise | 407 | 7,6% |
| InBody metric | 15 | 0,28% |
| Medical safety | 4 | 0,07% |
| General health | 1 | 0,02% |

**Tác động**

Đề tài tập trung InBody và tư vấn an toàn, nhưng corpus hầu như là nutrition/food. Retrieval rất dễ thiên về món ăn hoặc thông tin dinh dưỡng, trong khi kiến thức InBody và safety dựa trên vài seed document đang có `review_status="draft"`.

**Khuyến nghị**

- Không dùng số lượng document làm đại diện cho chất lượng.
- Xây corpus InBody có taxonomy theo chỉ số, giới tính, tuổi, giới hạn BIA, hydration, contraindication và interpretation.
- Có chuyên gia duyệt seed docs; đổi trạng thái chỉ khi đã review.
- Cân bằng candidate retrieval theo domain hoặc dùng domain router/filter.
- Thêm hard-negative và benchmark theo từng nhóm câu hỏi.

### 5.11. P1 – Privacy và quản trị dữ liệu chưa được thiết kế

**Bằng chứng**

- Lưu tên, email, giới tính, năm sinh, bệnh nền và chỉ số sức khỏe dạng rõ trong PostgreSQL.
- Log ghi user ID và kết quả health tool.
- Profile/bệnh nền có thể được gửi đến OpenAI/custom LLM; query sức khỏe có thể gửi Tavily; Cohere có thể nhận retrieved documents khi rerank.
- Không thấy consent, retention, delete/export account, encryption policy hoặc provider data policy.

**Tác động**

Ngay cả khi database không bị truy cập trái phép, dữ liệu vẫn có thể rò qua log hoặc nhà cung cấp bên thứ ba. Đây là phần dễ bị bỏ sót khi chỉ tập trung vào RAG.

**Khuyến nghị**

- Data minimization và consent rõ ràng trước khi gửi dữ liệu ra provider.
- Redact PII/health data khỏi log.
- Mã hóa in transit và at rest; quản lý key tách biệt.
- Thiết kế retention, delete, export và audit.
- Cho phép cấu hình local-only, không tự động fallback sang external provider nếu chưa có consent.

### 5.12. P2 – Chat history schema tồn tại nhưng flow chính không lưu

`models.py` có `ChatSession`, `ChatMessage` và helper persistence, nhưng sync chat gọi thẳng `multi_agent_handle()` và không lưu tin nhắn. Async task cũng ghi rõ chưa lưu DB. Frontend chỉ giữ lịch sử trong `st.session_state`; nút “Xóa hội thoại” chỉ xóa phiên trình duyệt.

Do đó:

- “Lưu lịch sử” chưa phải tính năng hoàn chỉnh.
- Đổi browser/session sẽ mất hội thoại.
- Không có conversation ownership, pagination, retention hoặc delete thật.

Khuyến nghị: hoặc tích hợp persistence end-to-end, hoặc mô tả đúng là “lịch sử trong phiên”.

### 5.13. P2 – Health check báo “healthy” quá lạc quan

`/health` luôn trả `"status": "healthy"` và chỉ trả:

- Cache đang dùng Redis hay memory.
- Search stats trong RAM.
- Agent capability tĩnh.

Endpoint không kiểm tra PostgreSQL, Qdrant, embedding model, Celery worker, LLM hoặc Tavily. Một hệ thống chỉ còn fallback vẫn có thể báo healthy.

Khuyến nghị:

- Tách `/live` và `/ready`.
- Readiness kiểm tra dependency bắt buộc theo mode cấu hình.
- Trả `healthy`, `degraded`, `unhealthy`.
- Không expose quá nhiều nội bộ trên endpoint công khai.

### 5.14. P2 – Trích dẫn chưa đủ truy vết

Prompt yêu cầu trích `[1]`, `[2]`, nhưng formatter chỉ đưa `source` như `internal_seed`, không đưa `metadata.source_url`: `backend/src/agents/graph.py:469-478`.

Hậu quả:

- Người dùng không mở được nguồn thật.
- Model có thể gắn số citation nhưng citation không được kiểm chứng.
- Không có mapping citation -> source trong response schema.

Khuyến nghị: trả `citations[]` có `id`, `title`, `url`, `chunk_id`, `quote/span`, `retrieval_score`; chỉ cho phép citation từ candidate thực tế.

### 5.15. P2 – Frontend có rủi ro XSS/HTML injection và lộ lỗi kỹ thuật

- `unsafe_allow_html=True` được dùng với `user_id`, title và source có thể đến từ input/corpus.
- Streamlit render raw HTML ở Search/System.
- Exception từ backend được hiển thị trực tiếp cho người dùng.
- Backend cũng trả `detail=str(e)` tại nhiều endpoint.

Khuyến nghị:

- Escape mọi giá trị động hoặc dùng component không cần raw HTML.
- Trả mã lỗi ổn định cho client; log stack trace ở server.
- Không đưa connection string, provider error hay internal path ra response.

### 5.16. P2 – Data pipeline chưa tái lập được từ clean clone

- Raw dataset và generated corpus bị `.gitignore`.
- `source_manifest.json` trong workspace hiện có path, nhưng không có đầy đủ URL tải, license, checksum, version và điều khoản sử dụng.
- Báo cáo build chứa absolute path của máy đánh giá.
- Không thấy download script cho toàn bộ raw sources.

Khuyến nghị:

- Manifest có `source_url`, `license`, `retrieved_at`, `sha256`, `version`.
- Tạo script download/build idempotent.
- Report chỉ dùng path relative.
- Dùng DVC, object storage hoặc artifact registry cho data versioning.
- Tạo data card mô tả bias, license, PII và giới hạn sử dụng.

### 5.17. P2 – Dependency và image chưa tái lập tốt

- Backend requirements trộn exact pin và range rộng; có nhiều package MySQL dù runtime dùng PostgreSQL.
- Embedding requirements dùng nhiều range không có upper bound.
- Không có lock file hoặc hash.
- Frontend cài lại requirements mỗi lần container startup: `frontend/entrypoint.sh:44-48`.
- Build tools được giữ trong backend runtime image.

Khuyến nghị:

- Dùng lock file và dependency update bot.
- Multi-stage build; runtime image nhỏ, non-root.
- Không `pip install` lúc container startup.
- Loại package/database driver không dùng.
- Pin base image và service image.

### 5.18. P2 – Observability gần như chưa có

Thư mục `monitoring/` rỗng. Hệ thống có log và `agent_trace`, nhưng chưa có:

- Request ID xuyên service.
- Latency từng agent/tool/provider.
- Token/cost.
- Retrieval hit rate và score distribution.
- Error rate, fallback rate, urgent query rate.
- PII redaction.
- Metrics/trace export.

Khuyến nghị: OpenTelemetry + Prometheus metrics, structured JSON logs, correlation ID và dashboard tối thiểu cho chat latency, dependency status, retrieval quality và safety.

### 5.19. P3 – Tài liệu còn mâu thuẫn với mã thực tế

Ví dụ:

- README nói FastAPI có streaming chat, nhưng không có endpoint streaming.
- README liệt kê Celery cho OCR/vectorize/PDF report, nhưng OCR/PDF report chưa được triển khai.
- Sơ đồ làm người đọc hiểu các agent phân nhánh, trong khi graph nối tuần tự.
- `config/settings.yaml` mô tả model/vector khác runtime.
- Một số docs cũ còn dấu vết prototype legal chatbot.
- `frontend/strimlit`, `llm/`, `monitoring/` là thư mục rỗng; `strimlit` còn sai chính tả.

Khuyến nghị: tách rõ `Implemented`, `Partial`, `Roadmap`; tạo một architecture decision record và tự động sinh API docs từ code.

## 6. Nhận xét theo thành phần

### 6.1. Backend FastAPI

**Tốt**

- Endpoint được nhóm theo chat, personalization, search, indexing và tools.
- Dùng Pydantic, giới hạn `SearchRequest.limit` và `days_per_week`.
- Có sync/async option và fallback khi Celery không khả dụng.

**Cần cải thiện**

- Authentication, authorization, rate limit, payload size limit.
- Không dùng blocking I/O trong async handler.
- Tách admin API khỏi public API.
- Exception handler tập trung, error code thống nhất.
- Lifespan hook để readiness/migration/index initialization.
- API versioning.

### 6.2. Agent orchestration

**Tốt**

- Shared state và agent trace dễ demo/debug.
- Specialist tool results được tách khỏi composer.
- Có fallback runner khi thiếu LangGraph.

**Cần cải thiện**

- Conditional edges thay vì nối tuần tự mọi node.
- Schema output typed cho từng agent.
- Không để LLM composer quyết định lại các kết quả deterministic.
- Chặn prompt injection từ profile, document và web.
- Output safety validation.
- Evaluation theo route/agent selection accuracy.

### 6.3. RAG

**Tốt**

- Có dense + BM25 + rerank.
- Có query expansion và metadata content type.
- Qdrant payload không trả vector gốc khi search.

**Cần cải thiện**

- Persistent/shared lexical index.
- Threshold/abstention; hiện vector search mặc định `score_threshold=0`.
- Calibrate score fusion thay vì bonus heuristic cố định.
- Domain-aware retrieval.
- Citation mapping và source quality scoring.
- Dedup theo stable chunk/document ID.
- Offline benchmark và regression set.

### 6.4. Health tools và safety

**Tốt**

- Công thức và rule tách riêng, dễ kiểm thử.
- Có disclaimer và urgent keyword cơ bản.
- BMI có nhắc giới hạn của chỉ số.

**Cần cải thiện**

- Nguồn khoa học/version cho từng threshold.
- Validation giá trị sinh lý và đơn vị.
- Phân tầng theo tuổi/giới tính khi phù hợp.
- Không giả lập cân nặng hoặc mục tiêu.
- Clinical review và post-generation enforcement.

### 6.5. Database và personalization

**Tốt**

- Schema bao quát roadmap.
- UUID, foreign key và một số index hợp lý.
- `session_scope` rollback đúng khi exception.

**Cần cải thiện**

- Alembic migration thay cho chỉ `init.sql`.
- Unique/constraint cho measurement khi cần.
- Row ownership và auth.
- Encryption, retention, delete/export và audit.
- Không auto-create user bằng GET vì GET nên không có side effect.
- Tích hợp chat persistence thật.

### 6.6. Frontend

**Tốt**

- UI thể hiện rõ đây là lời khuyên tham khảo.
- Có agent trace, health check, search và dev tools.
- Không giả vờ có upload khi backend chưa hỗ trợ.

**Cần cải thiện**

- Login/session identity thật.
- Không cho sửa `user_id` tự do.
- Bật XSRF, escape HTML.
- Ẩn dev tools trong production.
- Không hiển thị exception nội bộ.
- Tạo UI profile/measurement/history nếu tuyên bố cá nhân hóa.
- Accessibility test và responsive test.

### 6.7. Embedding service

**Tốt**

- API nhỏ, có `/health`, batch limit và model dimension.
- Container có healthcheck và log rotation trong Compose.

**Cần cải thiện**

- Auth/internal-only network và request text-length limit.
- Production WSGI server thay cho Flask development server.
- Worker/concurrency strategy phù hợp model.
- Input type validation từng phần tử.
- Rate limit, metrics, warmup và graceful shutdown.
- Pin model revision và checksum.

### 6.8. Data pipeline

**Tốt**

- Tách raw/processed/RAG/recommender.
- Không đưa ratings vào RAG.
- Có validation required fields và báo cáo build.
- Có metadata source cho seed docs.

**Cần cải thiện**

- Data versioning/reproducibility/license.
- Chất lượng PDF extraction và OCR noise test.
- Semantic chunking/table-aware parsing cho tài liệu dinh dưỡng.
- Clinical review.
- Cân bằng corpus và benchmark.
- Idempotent ingest và transactional reindex.

### 6.9. Infrastructure và vận hành

**Tốt**

- Compose chia service rõ.
- Có volume cho dữ liệu.
- Có embedding healthcheck.

**Cần cải thiện**

- Secrets, TLS, non-root, private network.
- Healthcheck cho mọi dependency.
- Resource limit, backup/restore và disaster recovery.
- Migration/reindex runbook.
- CI/CD thực tế thay vì chỉ có tài liệu hướng dẫn.
- Monitoring/SLO.

## 7. Những giả định hoặc khoảng trống dễ bị bỏ sót

1. **Có LangGraph không đồng nghĩa với multi-agent thông minh.** Chất lượng phụ thuộc routing, tools, data và evaluation; hiện graph chủ yếu là pipeline tuần tự.
2. **Có RAG không đồng nghĩa câu trả lời grounded.** Chưa có threshold, citation verification hoặc groundedness benchmark.
3. **Có disclaimer không đồng nghĩa an toàn y tế.** Disclaimer không ngăn model sinh lời khuyên sai.
4. **5.345 documents không đồng nghĩa corpus tốt.** 92% là nutrition và chỉ có 15 document InBody.
5. **Có schema chat không đồng nghĩa đã lưu lịch sử.** Flow chính chưa gọi các helper persistence.
6. **Health endpoint trả 200 không đồng nghĩa hệ thống sẵn sàng.** Nó không kiểm tra phần lớn dependency.
7. **Chạy được trên máy dev không đồng nghĩa tái lập được.** Raw data bị ignore, manifest thiếu provenance đầy đủ và dependency chưa lock.
8. **Cá nhân hóa có chi phí privacy.** Profile/bệnh nền có thể được gửi tới provider bên ngoài; cần consent và data minimization.
9. **OCR >85% chưa đủ cho dữ liệu y tế.** Cần metric theo từng field quan trọng, đặc biệt lỗi số thập phân, đơn vị và nhầm nhãn; accuracy trung bình có thể che lỗi nguy hiểm.
10. **Mỡ nội tạng level không phải chuẩn tuyệt đối giữa mọi thiết bị.** Rule phải biết model thiết bị/scale, không nên áp dụng một threshold chung mà không lưu provenance đo.

## 8. Roadmap khuyến nghị

### Giai đoạn 0 – Chốt phạm vi demo

- Đóng băng feature.
- Ghi rõ text-only MVP; OCR là roadmap.
- Chọn một LLM mode và một embedding model.
- Tạo 30–50 kịch bản demo/golden test.

**Điều kiện hoàn thành:** clean setup chạy được theo một tài liệu duy nhất; không còn cấu hình 384/1024 mâu thuẫn.

### Giai đoạn 1 – Sửa nền tảng RAG và test

- Sửa BM25 shared/persistent.
- Tạo index build artifact và kiểm tra đủ 5.345 documents.
- Thêm unit/integration tests.
- Tạo retrieval benchmark theo 5 content types.
- Thêm citation objects và score threshold.

**Điều kiện hoàn thành:** kết quả giống nhau giữa 2 workers; ingest theo batch không làm mất BM25; benchmark có baseline được lưu.

### Giai đoạn 2 – Safety và correctness

- Validate input.
- Không dùng dữ liệu mặc định để tạo khuyến nghị định lượng.
- Tạo urgent deterministic response.
- Output safety validator.
- Clinical review health tools và seed docs.
- Red-team suite tiếng Việt.

**Điều kiện hoàn thành:** urgent recall và harmful-answer rate đạt ngưỡng đã thống nhất với chuyên gia.

### Giai đoạn 3 – Security và privacy

- Authentication/authorization.
- Tách admin ingest.
- Private network cho DB/Valkey/Qdrant/embedding.
- Secret manager, TLS, log redaction.
- Consent, retention, delete/export, audit.

**Điều kiện hoàn thành:** không thể đọc/sửa dữ liệu người khác bằng cách đổi `user_id`; security test pass.

### Giai đoạn 4 – OCR đúng trọng tâm đề tài

- Upload an toàn, antivirus/file limits.
- OCR + layout parsing.
- Lưu raw file và parsed measurement có provenance.
- Field-level confidence và human correction UI.
- Dataset test đa mẫu máy/ảnh.

**Điều kiện hoàn thành:** báo cáo accuracy theo từng field, không chỉ accuracy trung bình; có quy trình xử lý confidence thấp.

### Giai đoạn 5 – Production hardening

- Non-root/pinned images/locked dependencies.
- Migration, backup/restore.
- Metrics, trace, alert và SLO.
- Load test, chaos/failure test.
- Canary deployment và rollback.

## 9. Bộ tiêu chí nghiệm thu đề xuất

### Chức năng

- Chat sync và async giữ cùng ngữ cảnh.
- Profile/measurement thuộc đúng authenticated user.
- RAG trả citation mở được.
- OCR field quan trọng có confidence và sửa tay.

### RAG

- BM25 document count đúng trên mọi replica.
- Không mất index sau ingest nhiều batch.
- Recall@5/MRR đạt baseline đã định.
- Có abstention khi không đủ nguồn.

### Safety

- Câu urgent luôn dùng response template ưu tiên hành động khẩn cấp.
- Không đưa liều thuốc/chẩn đoán ngoài policy.
- Output validator kiểm tra mọi câu trả lời.
- Golden/red-team suite chạy trong CI.

### Security/privacy

- Không endpoint dữ liệu hoặc ingest nào truy cập ẩn danh.
- Không đổi `user_id` để truy cập dữ liệu người khác.
- Không log bệnh nền/chỉ số sức khỏe ở dạng rõ.
- Có delete/export/audit.

### Vận hành

- `/live` và `/ready` phản ánh đúng dependency.
- Container chạy non-root.
- Restore PostgreSQL/Qdrant được diễn tập.
- Dashboard có latency, errors, fallback, retrieval và safety metrics.

## 10. Kết luận cuối

Repository cho thấy nhóm đã xây được một nền móng MVP tương đối rộng: chat UI, FastAPI, agent orchestration, health tools, personalization schema, hybrid retrieval, embedding service và data pipeline. Đây là khối lượng triển khai đáng kể và đủ để giải thích kiến trúc trong đồ án.

Tuy nhiên, ba tuyên bố quan trọng nhất của hệ thống vẫn chưa có bằng chứng tương ứng:

1. **“Hybrid RAG”** chưa đáng tin cậy vì BM25 bị giới hạn theo process/batch.
2. **“An toàn sức khỏe”** mới dừng ở keyword đầu vào và disclaimer, chưa kiểm soát output.
3. **“Cá nhân hóa”** chưa an toàn vì không có identity/authorization và một số agent dùng dữ liệu mặc định.

Ưu tiên hợp lý không phải thêm nhiều agent hoặc model hơn, mà là làm cho phần hiện có **đúng, đo được, an toàn và tái lập được**. Sau khi sửa RAG indexing, thêm test/benchmark và bảo vệ dữ liệu sức khỏe, hệ thống mới nên mở rộng sang OCR và triển khai cho người dùng thật.

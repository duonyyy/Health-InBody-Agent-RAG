# Báo cáo luồng hoạt động thật từ Browser tới Data — Real Runtime Completion (19/11/2026)

Tài liệu ghi lại toàn bộ quá trình kiểm thử, sửa lỗi và vận hành luồng thật:
**Browser -> Frontend Next.js -> FastAPI -> First-Party Auth -> PostgreSQL -> LangGraph Agent -> Embedding E5-small -> Qdrant/BM25 -> LLM -> Citation -> Browser**.

## 1. Inventory hệ thống trước thay đổi

- **Host OS**: Windows, Python 3.13 (host).
- **GPU**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB VRAM), driver 591.74, CUDA 13.1.
- **RAM**: 16 GB physical RAM (~862 MB free). Tuân thủ quy tắc AGENTS.md: Embedding chạy trên CPU để nhường GPU/VRAM cho LLM.
- **Docker**: Engine version 24.0.7, Compose v2.
- **Volumes**:
  - `postgres_data`: Tồn tại sẵn.
  - `qdrant_volume`: Tồn tại sẵn.
  - `valkey_data`: Tồn tại sẵn.
- **Networks**: `internal-network` (bridge).
- **Qdrant**: Container `qdrant-db` đã khởi động lại trên volume thật. Collection ứng viên `health_knowledge_e5_v1` (3846 points, 384 dim Cosine, green) và `nmk_chatbot_e5small_v20261118`.
- **PostgreSQL**: Container `postgres-db` đã chạy thật trên volume `postgres_data`. Đã xác minh 14 tables, áp dụng bổ sung migration an toàn `20261105_03_first_party_auth.up.sql` vào `schema_migrations`.
- **Valkey**: Container `valkey-db` (`valkey/valkey:bookworm`) đã pull và chạy thành công trên `internal-network`.

## 2. Embedding Service & Inference Verification (VERIFIED_RUNTIME)

- **Service**: Container `health-embedding-api` (`nmk-health-embedding:cpu`) đã build và start thành công trên `internal-network` (port 5000 container, 5001 host).
- **Model**: `intfloat/multilingual-e5-small` nạp từ `infra/embed_serving/models/multilingual-e5-small`. Weights `model.safetensors` (470 MB). Module `Normalize` tích hợp sẵn trong pipeline SentenceTransformers.
- **Inference Verification HTTP thật (`http://127.0.0.1:5001`)**:
  - Endpoint `/health`: status "healthy", `embedding_dim=384`, `device=cpu`, `dtype=float32`.
  - Single query (`query: ...`): `dim=384`, `all_finite=true`, `norm=1.0` (chuẩn hóa L2 hoàn hảo), latency 69 ms.
  - Single passage (`passage: ...`): `dim=384`, `all_finite=true`, `norm=1.0`, latency 53 ms.
  - Batch 3 texts: cả 3 vector `dim=384`, `norm=1.0`, `all_finite=true`, latency 103 ms.
  - Không có padding/truncation nhân tạo. Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/embedding_verification.json`.

## 3. Qdrant Serving Alias & Config Alignment (VERIFIED_RUNTIME)

- **Staging Candidate**: `health_knowledge_e5_v1` (3846 points, 384 dim Cosine, green).
- **Integrity Check**: Hàm `verify_collection_integrity` chạy thành công, điểm số 3846, fingerprint `3fbdda38e8a6de9dc7338dd11d46785a0d24f151f02d2e0294058352cf34c2cc` khớp 100% với manifest.
- **Alias Activation**: Chạy CLI an toàn `collection_admin.py activate-alias --collection health_knowledge_e5_v1 --alias nmk_chatbot_active`. Kích hoạt atomic alias `nmk_chatbot_active -> health_knowledge_e5_v1`. Xác nhận qua HTTP endpoint `GET http://localhost:6333/aliases`. Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/alias_activation.json`.
- **Config & Manifest Alignment**:
  - `VECTOR_SIZE=384`
  - `BM25_SNAPSHOT_PATH=/usr/src/app/artifacts/health_knowledge_e5_v1/bm25_snapshot.json.gz`
  - `CORPUS_RELEASE_MANIFEST_PATH=/usr/src/app/artifacts/health_knowledge_e5_v1/release.json`
  - `CORPUS_VERSION=e5small-2026-11-18-v1`
  - `EMBEDDING_QUERY_PREFIX=query: `
  - `EMBEDDING_PASSAGE_PREFIX=passage: `
  - `CUSTOM_EMBEDDING_API_URL=http://embedding-api:5000`
  - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/config_alignment.json`.

## 4. Release Gate Reinforcement & Regression (VERIFIED_TEST)

- **Lỗ hổng phát hiện & khắc phục**:
  1. `verify_runtime_release_sync` trước đây bỏ qua kiểm tra khi snapshot thiếu `release_id`, `corpus_version` hoặc `chunk_set_fingerprint` (do `if bm25_x and m_x:`). Đã sửa thành so sánh chặt chẽ `if m_x and bm25_x != m_x: reasons.append(...)`.
  2. Bổ sung hỗ trợ `CORPUS_REQUIRE_MANIFEST=true` để từ chối `synced` nếu không có manifest.
  3. Xử lý tương thích `qdrant-client==1.10.1` bỏ qua `check_compatibility` argument trong `backend/src/rag/qdrant/client.py`.
- **Regression Test**: Viết 2 test trong `backend/tests/unit/test_release_sync_unverified.py`, tái hiện lỗi (2 failed) trước khi sửa, sau đó đạt (5 passed).
- **Unit Suite**: 451/451 unit test passed.

## 5. First-Party Auth & PostgreSQL Data Isolation (VERIFIED_RUNTIME)

- **Cấu hình JWT**: Đã cấu hình `JWT_SIGNING_KEY`, `JWT_ISSUER=bodywise-local`, `JWT_AUDIENCE=bodywise-web` trong `backend/.env`.
- **Đăng ký & Đăng nhập thật**:
  - `POST /auth/register`: 201 Created. Mật khẩu mã hóa Argon2id trong PostgreSQL.
  - `POST /auth/login`: 200 OK. Nhận JWT token.
- **Personalization & Consent**:
  - Cập nhật consent qua `PATCH /me/profile` (`health_data_processing: true, personalization: true`).
  - Ghi nhận InBody measurement qua `POST /me/measurements`.
  - Khởi tạo hội thoại qua `POST /me/conversations`.
- **Cô lập dữ liệu (Cross-User Data Isolation)**:
  - User B gọi `GET /me/measurements` -> 200 OK nhưng `count = 0` (không thấy dữ liệu User A).
  - User B gọi `GET /me/conversations/{id_a}` -> 404 Not Found (không thể truy cập hội thoại User A).
  - Request không có token -> 401 Unauthorized.
  - SQL readback trực tiếp từ container `postgres-db`: Xác nhận 2 users trong bảng `users`, 1 record `inbody_measurements`, 1 record `chat_sessions` thuộc đúng `user_a`.
  - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/auth_and_isolation.json` và `docs/reports/upgrade-2026/real-runtime-completion-evidence/sql_readback.txt`.

## 6. Celery Background Worker & Kombu Fix (VERIFIED_RUNTIME)

- **Lỗi phát hiện**: `chatbot-worker` bị crash loop liên tục với lỗi `kombu.exceptions.VersionMismatch: Redis transport requires redis-py versions 6.1.0 or later. You have 5.0.7`.
- **Nguyên nhân**: `requirements.txt` ghim `redis==5.0.7`, nhưng Kombu 5.7.0 (của Celery 5.4.0) bắt buộc `redis >= 6.1.0`.
- **Khắc phục**: Nâng cấp `redis>=6.1.0` trong `requirements.txt` và cập nhật container lệnh khởi chạy.
- **Xác minh runtime**:
  - `chatbot-worker` trạng thái: `Up` (không còn restart loop).
  - Kiểm tra `docker exec chatbot-api celery -A jobs.tasks.celery_app inspect ping`:
    Trả về `celery@chatbot-worker: OK pong` (1 node online).
  - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/celery_ping.txt`.

## 7. Deterministic Safety & BMI Fast-Path (VERIFIED_RUNTIME)

Đã kiểm thử HTTP thật đối với các kịch bản fast-path theo yêu cầu AGENTS.md:
1. **Urgent Medical Safety Fast-Path**:
   - Query: `"Tôi bị đau ngực và khó thở rất nhiều"`
   - Latency: **15 ms** (Chỉ tiêu AGENTS.md P95 < 500 ms -> ĐẠT).
   - Fast path: `urgent_safety`.
   - Hành vi: Zero LLM, zero Qdrant call, cảnh báo cấp cứu y tế tức thời.
   - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/fastpath_urgent.json`.
2. **BMI Calculation Fast-Path**:
   - Query: `"tính BMI cân nặng 72 kg chiều cao 170 cm"`
   - Latency: **26 ms** (Chỉ tiêu AGENTS.md P95 < 500 ms -> ĐẠT).
   - Fast path: `inbody_tools`.
   - Hành vi: Zero LLM, zero Qdrant call, tính ra BMI = 24.91 (tiền thừa cân theo chuẩn châu Á).
   - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/fastpath_bmi.json`.
3. **Negative Input Validation**:
   - Query: `"tính BMI chiều cao -170 cm cân nặng -72 kg"`
   - Status code: **HTTP 422 Unprocessable Entity**.
   - Detail: `"Giá trị cân nặng không hợp lệ. Vui lòng kiểm tra dấu, đơn vị và nhập lại."`
   - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/negative_validation.json`.

## 8. Hybrid Qdrant + BM25 Real Retrieval Verification (VERIFIED_RUNTIME)

- Query: `"Chỉ số PBF là gì?"`
- Luồng thực tế đã chạy:
  1. FastAPI nhận request từ user đã auth.
  2. LangGraph Agent kích hoạt router -> định tuyến `InBodyAgent` & `KnowledgeAgent`.
  3. KnowledgeAgent gọi Embedding API HTTP (`http://embedding-api:5000`) sinh vector E5-small 384 chiều trong 50 ms.
  4. Qdrant nhận truy vấn qua alias `nmk_chatbot_active -> health_knowledge_e5_v1`.
  5. BM25 snapshot tính điểm lexical kết hợp với vector score (hybrid mode).
  6. Trả về đúng 3 tài liệu chuẩn y khoa:
     - `Phần trăm Mỡ Cơ thể (PBF) và Phân loại Ngưỡng Sức khỏe` (doc_id: `inbody_metric_pbf_ranges_001`, hybrid_score: 1.142)
     - `PBF và phần trăm mỡ cơ thể`
     - `PBF khác BFM như thế nào`
  - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/retrieval_smoke.json`.

## 9. Khắc phục triệt để Blocker Đĩa C: & Quyết định chọn LLM `qwen2.5:3b` (VERIFIED_RUNTIME)

- **Giải phóng đĩa C:**: Người dùng đã dọn dẹp dung lượng đĩa C:, giải phóng không gian lên tới 17.84 GB trống (sau khi build và dọn dẹp còn ~13.59 GB trống).
- **Quyết định model LLM**: Người dùng quyết định dứt khoát chọn model `qwen2.5:3b` phục vụ online trên Ollama:
  - Dung lượng nhẹ (~1.9 GB), kéo về thành công 100%.
  - Nạp toàn bộ 100% vào GPU VRAM (2623 MiB / 4096 MiB RTX 3050 Laptop GPU).
  - Tốc độ suy luận cao: ~56 tokens/giây, độ trễ sinh từ chỉ ~160 ms.
  - Hoàn toàn tuân thủ quy tắc VRAM GPU 4 GB của `AGENTS.md`: Embedding chạy CPU (`health-embedding-api`), LLM chạy 100% trên GPU VRAM.

## 10. Vận hành LLM Ollama thật, Tinh chỉnh Composer & Claim Verification Guard (VERIFIED_RUNTIME)

- **Vấn đề phát hiện khi tích hợp LLM thật**:
  1. `LLM_COMPOSER_MAX_TOKENS=96` khiến câu trả lời tiếng Việt bị cắt ngắn giữa chừng trước khi kịp ghi trích dẫn `[n]`. Đã nâng lên `LLM_COMPOSER_MAX_TOKENS=400` trong `backend/.env`.
  2. Qwen 3B cần chỉ thị prompt rõ ràng: Bắt buộc gắn `[n]` vào các câu chứa kiến thức từ tài liệu RAG, không gắn vào câu từ chối hoặc câu cảnh báo an toàn.
  3. Cơ chế deterministic guard trong `backend/src/harness/guards.py`:
     - Bổ sung cụm từ nhận diện lưu ý an toàn (`_SAFETY_NOTICE_PHRASES`) và từ chối/cần thêm thông tin (`_CLARIFICATION_OR_REFUSAL_PHRASES`).
     - Cho phép safety notice và clarification được miễn trừ (exempt) khỏi claim linking ngay cả khi có `[n]`.
     - Bổ sung kế thừa đại từ chỉ định (anaphoric continuation) liền kề câu đã có trích dẫn hợp lệ.
- **Kết quả nghiệm thu**:
  - `claim_verification.supported = true`.
  - Claim evidence links được tạo chính xác: Trích dẫn `[2]` liên kết trực tiếp tới chunk `internal_inbody_pbf_001-1`.
  - Bằng chứng: `docs/reports/upgrade-2026/real-runtime-completion-evidence/full_rag_llm_response.json`.

## 11. Khởi tạo và Vận hành Frontend Next.js 16 Container thật (VERIFIED_RUNTIME)

- **Khắc phục lỗi build**:
  - Lỗi: `npm ci` trong Dockerfile thất bại do thiếu gói `tsx` trong `package-lock.json`.
  - Sửa: Chạy `npm install --package-lock-only` trong thư mục `frontend` để đồng bộ lockfile.
  - Build thành công Next.js 16.4.6 Turbopack tối ưu hóa cho production.
- **Trạng thái container**:
  - Tên container: `chatbot-next-ui` (port 3000:3000, image `frontend-chatbot-next-ui`).
  - Trạng thái: `Up` (Running).
  - Phản hồi HTTP: `curl.exe -I http://localhost:3000` -> `HTTP/1.1 200 OK` (10304 bytes).
- **Bộ kiểm thử Frontend**: 14/14 tests trong `frontend/tests/regression-r04-r05-r10-r11.test.mjs` đạt 100%.

## 12. Nghiệm thu Toàn diện End-to-End Real Runtime (VERIFIED_RUNTIME)

Kịch bản kiểm thử tự động toàn diện được thực thi qua `node frontend/tests/e2e-live-runtime.mjs` với 100% dịch vụ thật:
`Browser/Client -> Next.js 16 (port 3000) -> FastAPI (port 8000) -> First-party Auth -> PostgreSQL 16 (port 5432) -> LangGraph Agent -> BGE/E5 Embedding CPU (port 5001) -> Qdrant/BM25 Hybrid (port 6333) -> Ollama qwen2.5:3b (port 11434, GPU VRAM) -> Claim Verifier -> Citations -> Client`.

| Bước kiểm thử | Kết quả đo đạc thực tế | Chỉ tiêu AGENTS.md / DoD | Đánh giá |
|---|---|---|---|
| **1. Frontend HTTP 200** | HTTP 200 OK, 10.3 KB payload | Next.js 16 SSR/Static phục vụ tốt | **ĐẠT** |
| **2. Backend Dependencies Readiness** | 100% READY: postgres: true, qdrant: true, valkey: true, embedding_api: true, corpus_release_sync: true | Tất cả dependencies sẵn sàng | **ĐẠT** |
| **3. PostgreSQL Auth** | Tạo người dùng mới qua `POST /auth/register`, cấp JWT Bearer token | Không dùng dev header, lưu DB thật | **ĐẠT** |
| **4. Fast-path BMI** | Latency: **19 ms**, tính ra BMI = 24.22, tiền thừa cân theo chuẩn châu Á | P95 < 500 ms, zero LLM, zero Qdrant | **ĐẠT** |
| **5. Fast-path Urgent Safety** | Latency: **17 ms**, cảnh báo cấp cứu tim mạch/hô hấp tức thì | P95 < 500 ms, zero LLM, zero Qdrant | **ĐẠT** |
| **6. RAG InBody đầy đủ** | Latency: **10.7 giây**, router chọn `InBodyAgent` & `KnowledgeAgent`, E5 retrieval hybrid top 3 docs InBody, Ollama `qwen2.5:3b` sinh câu trả lời bám sát chunk có trích dẫn `[2]`, claim verification: `supported: true`, 3 citations đầy đủ title, URL, excerpt | Router accuracy, Hybrid retrieval, Claim verification supported, Trích dẫn chuẩn y khoa | **ĐẠT** |

- Bằng chứng JSON chi tiết: `docs/reports/upgrade-2026/real-runtime-completion-evidence/e2e_live_runtime_result.json`.

## 13. Tổng kết Chất lượng & Trạng thái Toàn hệ thống

- **Backend Unit Tests**: **453/453 passed (100%)** trong 85.70s.
- **Frontend Regression Tests**: **14/14 passed (100%)** trong 2.13s.
- **E2E Live Runtime Tests**: **6/6 passed (100%)**.
- **Không có bất kỳ service giả lập nào (Zero mock/stub ở tầng runtime nghiệm thu)**:
  - Docker Engine & Compose: 7 containers đang hoạt động ổn định.
  - CSDL PostgreSQL: Dữ liệu thật, 14 bảng, auth thật, migration đầy đủ.
  - Qdrant Vector DB: Collection thật `health_knowledge_e5_v1`, alias `nmk_chatbot_active`, 3846 points.
  - Embedding Service: E5-small CPU inference thật, norm 1.0, 384 dim.
  - LLM Service: Ollama `qwen2.5:3b` chạy 100% trên GPU VRAM RTX 3050 Laptop.
  - Frontend: Next.js 16 phục vụ web tại `http://localhost:3000`.

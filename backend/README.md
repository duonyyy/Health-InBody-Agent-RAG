# Backend - Health/InBody Agent RAG

Backend là dịch vụ API lõi cho hệ thống Health/InBody Multi-Agent RAG MVP, được xây dựng bằng **FastAPI**. Dịch vụ này đảm nhiệm việc tiếp nhận request từ người dùng, quản lý hồ sơ sức khỏe (Personalization), điều phối hệ thống Agent qua **LangGraph**, truy xuất kiến thức (Hybrid Search), gọi các công cụ y tế và sinh câu trả lời an toàn.

> **Lưu ý phạm vi:** Source có gateway có xác thực `POST /me/inbody-ocr` tới dịch vụ OCR nội bộ, nhưng `FEATURE_OCR_UPLOAD` mặc định tắt. Chưa kiểm chứng runtime hoặc độ đúng OCR trên phiếu thật.

## 1. Vai Trò Của Backend

Backend thực hiện các chức năng chính:
- Cung cấp REST API cho Frontend (Chat, Health Tools, Search, User Profile, Measurements).
- Quản lý luồng **Multi-Agent** bằng LangGraph.
- Hỗ trợ **Personalization**: Tự động lấy hồ sơ người dùng (tuổi, giới tính, mục tiêu, bệnh nền) và lịch sử đo InBody gần nhất làm ngữ cảnh.
- Điều hướng Agent (Normalizer -> Supervisor -> Chuyên gia -> Safety -> Composer).
- Xử lý **Hybrid Retrieval**: Kết hợp Vector Search (Qdrant) và Keyword Search (BM25), sau đó xếp hạng lại (Reranker).
- Gọi các công cụ phân tích sức khỏe: tính BMI, mỡ cơ thể, mỡ nội tạng, gợi ý dinh dưỡng và luyện tập.
- **Guardrail y tế**: Chạy agent an toàn để cảnh báo rủi ro, không chẩn đoán bệnh thay bác sĩ.

## 2. Kiến Trúc Thư Mục

```text
backend/
├── src/
│   ├── api/                   # FastAPI app, routes và request schemas
│   ├── agents/                # LangGraph Multi-Agent
│   │   ├── __init__.py        #   Export multi_agent_handle, get_multi_agent_summary
│   │   ├── graph.py           #   Định nghĩa toàn bộ Agent nodes và LangGraph edges
│   │   ├── state.py           #   AgentState TypedDict, append_trace/append_error
│   │   └── parsing.py         #   Extract chỉ số (weight, height, PBF...) từ câu hỏi
│   ├── core/                  # Config, cache, logging và tiện ích dùng chung
│   ├── health/                # Health tools và safety/legal tools
│   ├── integrations/          # Tavily và dịch vụ bên ngoài
│   ├── jobs/                  # Celery tasks
│   ├── llm/                   # LLM client, embedding và summarizer
│   ├── persistence/           # PostgreSQL models, database, personalization
│   ├── pipelines/             # Import corpus vào staging
│   └── rag/                   # Retrieval, chunking, rerank và Qdrant client
├── data/
├── .dockerignore
├── .env.example               # Mẫu biến môi trường
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh              # Script khởi động container
├── import_data.sh             # Script shell import dữ liệu
└── requirements.txt
```

## 3. Luồng Xử Lý Multi-Agent (Thực Tế Mã Nguồn)

Luồng được điều phối chính qua LangGraph (`src/agents/graph.py`):

1. Auth/ownership đứng trước xử lý; deterministic urgent precheck đứng trước DB/history/queue/LLM/retrieval. Urgent trả hướng dẫn ngay; số đo tường minh sai trả 422 sau urgent.
2. ContextLoader lấy hồ sơ/lần đo đã xác nhận và lịch sử đúng owner. Graph chạy precheck với bệnh nền đã lưu; lời chào thuần/BMI đủ dữ liệu chỉ đi fast-path khi risk=low.
3. QuestionNormalizer chuẩn hóa follow-up; IntentRouter chọn ba specialist công khai: InBodyAgent (chỉ số), LifestyleAgent (nutrition/training), KnowledgeAgent (RAG/web/general chat). Các tên NutritionAgent/TrainingAgent/RAGAgent/WebSearchAgent/GeneralChatAgent là capability nội bộ.
4. Specialist ghi tool results/tài liệu vào shared state. Medical caution chỉ đi medical-safety retrieval, không tự lập kế hoạch hoặc gọi web.
5. SafetyGuard giữ risk thực và AnswerComposer tổng hợp câu trả lời/citation; fallback vẫn giữ recommended_action. Các workflow stage không phải specialist mới.

## 4. Các Biến Môi Trường (Environment Variables)

Hệ thống đọc từ file `.env` hoặc cấu hình trong `docker-compose.yml`.

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `QDRANT_URL` | `http://qdrant-db:6333` | Endpoint kết nối Vector DB Qdrant |
| `QDRANT_COLLECTION_NAME` | `nmk_chatbot_active` | Collection hoặc alias runtime đang phục vụ |
| `QDRANT_COLLECTION_ALIAS` | `nmk_chatbot_active` | Alias ổn định để chuyển collection blue/green |
| `CORPUS_VERSION` | trống | Phiên bản corpus bắt buộc khi import thật |
| `VECTOR_SIZE` | `1024` | Số chiều của vector (Tương thích model BGE-M3) |
| `CUSTOM_EMBEDDING_API_URL` | `http://host.docker.internal:5001` | Endpoint của service `embed_serving` |
| `DATABASE_URL` | `postgresql+psycopg2://...` | Chuỗi kết nối PostgreSQL lưu trữ Users, Measurements |
| `AUTH_MODE` | `production` | First-party JWT; development header chỉ bật tường minh ở local |
| `JWT_SIGNING_KEY` | trống | Secret ngẫu nhiên tối thiểu 32 byte; không in/log/đưa vào frontend |
| `JWT_ISSUER`, `JWT_AUDIENCE` | `bodywise-local`, `bodywise-web` trong template | Định danh first-party; phải cấu hình cả hai |
| `CORS_ALLOWED_ORIGINS` | localhost:3000 và 127.0.0.1:3000 trong template | Danh sách origin đầy đủ, phân tách bằng dấu phẩy; production không tự thêm origin |
| `LLM_PROVIDER` | `none` | Engine sinh ngôn ngữ (`ollama`, `openai`, `custom`, `none`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint của Ollama |
| `OLLAMA_MODEL` | trống | Chọn model đã cài khi dùng provider Ollama |
| `OPENAI_API_KEY` | *(trống)* | API Key nếu dùng model OpenAI |
| `TAVILY_API_KEY` | *(trống)* | API Key dùng cho WebSearchAgent |
| `LLM_RESPONSE_CACHE_ENABLED` | `true` | Bật cache exact-match cho câu định nghĩa chung BMI/PBF/SMM/BFM/InBody |
| `LLM_RESPONSE_CACHE_TTL_SECONDS` | `300` | TTL câu trả lời cache; key đổi theo prompt, model và corpus version |
| `CACHE_MEMORY_MAX_ENTRIES` | `256` | Giới hạn số mục cache RAM khi Valkey không sẵn sàng |
| `CACHE_REDIS_RETRY_SECONDS` | `5` | Khoảng chờ trước khi thử kết nối lại Valkey sau lỗi khởi động |

## 5. Hướng Dẫn Chạy Dịch Vụ

Làm theo [SETUP.md](../SETUP.md) để tạo secret không in ra console, cấu hình DATABASE_URL/POSTGRES_* khớp nhau, JWT và CORS. Template không có mật khẩu DB dùng chung. Không sinh password mới cho PostgreSQL volume đang có dữ liệu; rotation là đợt riêng.

Tại **repo root**, dùng cùng backend/.env cho nội suy Compose và container env_file:

```powershell
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml config --quiet
docker compose --env-file backend/.env -f backend/docker-compose.yml config --quiet
docker compose --env-file backend/.env -f backend/docker-compose.yml up --build -d
```

Khởi động infra trước theo SETUP. Không in toàn bộ compose config vì chứa secret. Biến shell trùng tên có thể ghi đè --env-file; kiểm tra AUTH_MODE/LLM_PROVIDER/DATABASE_URL và xóa override không chủ ý trong shell. API/worker/scheduler đều nhận cùng credential; endpoint nội bộ dùng DNS Docker, client chạy trên host mới dùng localhost.
Dịch vụ API sẽ hoạt động tại: `http://localhost:8000` (Truy cập `http://localhost:8000/docs` để xem Swagger UI).

## 6. Các API Endpoints Chính

### System & Tools
| Method | Endpoint | Chức Năng |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness và thống kê cấu hình/cache/search; chưa chứng minh dependency sẵn sàng |
| `GET` | `/health/ready` | Probe dependency; 200 ready hoặc 503 degraded |
| `GET` | `/agent/tools` | Trả về thông tin hệ thống Multi-Agent (capabilities & schema) |
| `POST` | `/tools/...` | Các tools độc lập (`/bmi`, `/pbf`, `/visceral-fat`, `/nutrition`, `/training`, `/safety`) |
| `POST` | `/summarize` | Tóm tắt văn bản thông thường hoặc tóm tắt báo cáo sức khỏe |

### Quản Lý Người Dùng (Personalization)
| Method | Endpoint | Chức Năng |
| :--- | :--- | :--- |
| `GET/PUT/PATCH` | `/me/profile` | Hồ sơ và consent của authenticated user |
| `GET/PUT` | `/me/goals/current` | Active goal có version |
| `GET` | `/me/goals/history` | Lịch sử goal, không ghi đè version cũ |
| `GET/POST` | `/me/measurements` | Cursor list và tạo lần đo có provenance/confirmation |
| `GET/PATCH/DELETE` | `/me/measurements/{id}` | Owner-scoped CRUD; delete là soft delete |
| `GET` | `/me/progress/summary`, `/me/progress/timeline` | Delta từ confirmed, non-deleted records |
| `POST/GET` | `/me/plans`, `/me/plans/current` | Versioned plan + input snapshot/evidence/safety |
| `POST/GET` | `/me/check-ins` | Check-in và symptom safety route |

Các endpoint `/me` và chat không tin `user_id` trong body/path. Production dùng
Bearer JWT từ POST /auth/register hoặc /auth/login, xác minh HS256/signature/issuer/audience/time claims; trusted middleware cũng có thể inject `request.state.current_user`. Login cần PostgreSQL schema auth và Valkey rate limiter thật; dependency thiếu trả 503. Không cần IdP/JWKS ngoài cho cấu hình first-party này. Local-only:
`AUTH_MODE=development` cho phép header `X-Dev-User-Id`. Legacy
`/users/{user_id}/*` mặc định trả 404 và không dùng cho client mới.

### Chat & Search (Core)
| Method | Endpoint | Chức Năng |
| :--- | :--- | :--- |
| `POST` | `/chat/complete` | Xử lý tin nhắn và chạy luồng Multi-Agent (Hỗ trợ Sync/Async qua Celery) |
| `POST` | `/agent/answer` | Gọi agent trả lời trực tiếp không qua task |
| `POST` | `/search` | Thực hiện Hybrid Search (Vector + BM25 + Rerank) độc lập |
| `POST` | `/documents/index` | Nạp (index) nhiều tài liệu vào hệ thống Qdrant/BM25 |

## 7. Xử Lý Sự Cố Thường Gặp

- **Lỗi Celery timeout (`/chat/complete`):** Đảm bảo worker Celery và Redis đang chạy. Bạn có thể truyền `"sync_request": true` trong body để chạy đồng bộ bỏ qua Celery.
- **Không tìm thấy kết quả RAG:** Kiểm tra cấu hình `CUSTOM_EMBEDDING_API_URL`, đảm bảo `embed_serving` đang chạy, và collection trong Qdrant đã chứa dữ liệu.
- **Lỗi sinh văn bản (LLM):** Kiểm tra cấu hình `LLM_PROVIDER`. Nếu dùng Ollama, đảm bảo model đã được tải (`ollama run qwen2.5:3b`).

## 8. Bộ nhớ hội thoại & cá nhân hóa (PostgreSQL local)

Lịch sử hội thoại (`/me/conversations/*`), sở thích đã xác nhận (`/me/memory/facts/*`), hồ sơ/chỉ số/mục tiêu/kế hoạch/check-in và retention (`CHAT_RETENTION_DAYS`, Celery Beat `purge_memory`) được quản lý hoàn toàn trên **PostgreSQL** theo quyền sở hữu (owner-scoped) và consent local (`health_data_processing`, `personalization`).

Dự án **đã gỡ tích hợp Zep** (không dùng bộ nhớ ngoài hay các route `/me/memory-consent`, `/me/memory/sync`, `DELETE /me/memory`). Xem [hợp đồng bộ nhớ](src/memory/README.md) và [báo cáo gỡ tích hợp Zep](../docs/reports/upgrade-2026/remove-zep-2026-11-18.md).

# Backend - Health/InBody Agent RAG

Backend là dịch vụ API lõi cho hệ thống Health/InBody Multi-Agent RAG MVP, được xây dựng bằng **FastAPI**. Dịch vụ này đảm nhiệm việc tiếp nhận request từ người dùng, quản lý hồ sơ sức khỏe (Personalization), điều phối hệ thống Agent qua **LangGraph**, truy xuất kiến thức (Hybrid Search), gọi các công cụ y tế và sinh câu trả lời an toàn.

> **Lưu ý phạm vi:** Hệ thống hiện tại (MVP) tập trung xử lý dữ liệu người dùng nhập bằng văn bản và lưu trữ hồ sơ/lịch sử đo. Tính năng upload/OCR phân tích file ảnh báo cáo InBody trực tiếp chưa được expose.

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
│   ├── agents/                # LangGraph Multi-Agent
│   │   ├── __init__.py        #   Export multi_agent_handle, get_multi_agent_summary
│   │   ├── graph.py           #   Định nghĩa toàn bộ Agent nodes và LangGraph edges
│   │   ├── state.py           #   AgentState TypedDict, append_trace/append_error
│   │   └── parsing.py         #   Extract chỉ số (weight, height, PBF...) từ câu hỏi
│   ├── app.py                 # Khởi tạo FastAPI và toàn bộ REST Endpoints
│   ├── agent.py               # Wrapper tương thích ngược cho multi-agent handler
│   ├── brain.py               # Xử lý LLM (Ollama/OpenAI), prompt, detect intent/route
│   ├── cache.py               # Cache utilities dùng Redis/Valkey
│   ├── configs.py             # Hằng số dùng chung (collection name, vector size, DB URL)
│   ├── custom_embedding.py    # Client kết nối tới service embed_serving (BGE-M3)
│   ├── database.py            # Kết nối PostgreSQL bằng SQLAlchemy
│   ├── health_tools.py        # Logic tính BMI, PBF, mỡ nội tạng, dinh dưỡng, tập luyện, safety
│   ├── import_data.py         # Script nạp corpus từ data_pipeline vào Qdrant
│   ├── legal_tools.py         # Re-export tương thích ngược từ health_tools
│   ├── models.py              # Pydantic schemas + SQLAlchemy ORM models
│   ├── personalization.py     # Quản lý hồ sơ người dùng và lịch sử đo InBody
│   ├── query_rewriter.py      # Viết lại câu hỏi, mở rộng từ khóa y tế cho RAG
│   ├── rerank.py              # Xếp hạng lại tài liệu truy xuất (Cohere/fallback)
│   ├── search.py              # Hybrid search logic (Qdrant vector + BM25 + Rerank)
│   ├── splitter.py            # Tách document thành chunks cho indexing
│   ├── summarizer.py          # Tóm tắt văn bản / báo cáo sức khỏe bằng LLM
│   ├── tasks.py               # Tác vụ nền (Celery), indexing tài liệu
│   ├── tavily_tool.py         # Tìm kiếm web sức khỏe qua Tavily API
│   ├── utils.py               # Logging có màu, generate request ID
│   └── vectorize.py           # Thao tác với Vector DB Qdrant (create/upsert/search)
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

1. **Khởi tạo (PersonalizationContextAgent)**: Tự động tải hồ sơ cá nhân và lần đo InBody gần nhất của người dùng.
2. **QuestionNormalizerAgent**: Chuẩn hóa câu hỏi nếu có lịch sử trò chuyện.
3. **SupervisorAgent**: Phân loại và chọn các agent chuyên trách dựa trên nội dung câu hỏi:
   - `InBodyAgent`: Xử lý tính toán BMI, PBF, mỡ nội tạng.
   - `NutritionAgent`: Tính toán chiến lược dinh dưỡng.
   - `TrainingAgent`: Lên lịch tập luyện cơ bản.
   - `RAGAgent`: Truy xuất tài liệu nội bộ về sức khỏe.
   - `WebSearchAgent`: Tìm kiếm thông tin mới trên mạng (Tavily).
   - `GeneralChatAgent`: Trả lời các câu hỏi giao tiếp thông thường.
4. Các agent được gọi sẽ ghi kết quả xử lý (tool results, tài liệu, phân tích) vào *shared state*.
5. **SafetyAgent**: Luôn luôn chạy cuối cùng trong cụm chuyên trách để rà soát rủi ro y tế và thêm cảnh báo (dựa vào câu hỏi và tiền sử bệnh lý của người dùng).
6. **ResponseComposerAgent**: Đọc toàn bộ trạng thái (câu hỏi, agent output, tài liệu RAG, personalization, safety) và tổng hợp thành câu trả lời tiếng Việt cuối cùng.

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
| `LLM_PROVIDER` | `ollama` | Engine sinh ngôn ngữ (`ollama`, `openai`, `none`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint của Ollama |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model LLM sử dụng khi chạy nội bộ |
| `OPENAI_API_KEY` | *(trống)* | API Key nếu dùng model OpenAI |
| `TAVILY_API_KEY` | *(trống)* | API Key dùng cho WebSearchAgent |

## 5. Hướng Dẫn Chạy Dịch Vụ

Đứng tại thư mục `backend/`, chạy bằng Docker Compose:

```bash
docker compose up --build
```
Dịch vụ API sẽ hoạt động tại: `http://localhost:8000` (Truy cập `http://localhost:8000/docs` để xem Swagger UI).

## 6. Các API Endpoints Chính

### System & Tools
| Method | Endpoint | Chức Năng |
| :--- | :--- | :--- |
| `GET` | `/health` | Kiểm tra trạng thái của API, Qdrant, Cache, Agent |
| `GET` | `/agent/tools` | Trả về thông tin hệ thống Multi-Agent (capabilities & schema) |
| `POST` | `/tools/...` | Các tools độc lập (`/bmi`, `/pbf`, `/visceral-fat`, `/nutrition`, `/training`, `/safety`) |
| `POST` | `/summarize` | Tóm tắt văn bản thông thường hoặc tóm tắt báo cáo sức khỏe |

### Quản Lý Người Dùng (Personalization)
| Method | Endpoint | Chức Năng |
| :--- | :--- | :--- |
| `GET` | `/users/{user_id}/profile` | Lấy hồ sơ người dùng |
| `PUT` | `/users/{user_id}/profile` | Cập nhật hồ sơ (chiều cao, mục tiêu, bệnh nền...) |
| `GET` | `/users/{user_id}/measurements` | Lấy lịch sử đo InBody |
| `POST`| `/users/{user_id}/measurements` | Thêm mới một kết quả đo InBody |
| `GET` | `/users/{user_id}/personalization-context`| Lấy context tổng hợp của người dùng để đưa vào chat |

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

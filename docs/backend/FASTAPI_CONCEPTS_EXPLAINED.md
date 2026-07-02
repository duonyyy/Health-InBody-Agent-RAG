# Giải Thích FastAPI Backend

File `backend/src/app.py` là entrypoint FastAPI của dự án Health/InBody Agent RAG. File này định nghĩa các request schema bằng Pydantic, các endpoint chat, search, indexing, summarization và health tools.

## 1. FastAPI App

Ứng dụng được tạo với metadata:

```python
app = FastAPI(
    title="Health/InBody Agent RAG Backend",
    version="1.0.0-beta",
)
```

Khi chạy local hoặc Docker, API mặc định ở:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

## 2. Pydantic Request Models

FastAPI dùng Pydantic để validate JSON request.

### `CompleteRequest`

Dùng cho `/chat/complete`:

```json
{
  "bot_id": "health-inbody-agent",
  "user_id": "demo-user",
  "user_message": "BMI và PBF khác nhau thế nào?",
  "history": [],
  "sync_request": true
}
```

Các field bắt buộc:

- `user_id`
- `user_message`

### `SearchRequest`

Dùng cho `/search`:

```json
{
  "query": "mỡ nội tạng cao nên làm gì",
  "limit": 5,
  "use_rerank": true
}
```

`limit` được giới hạn từ 1 đến 20.

### `DocumentCreateRequest`

Dùng cho `/document/create` để index một document.

### `DocumentsIndexRequest`

Dùng cho `/documents/index` và `/data/import` để index nhiều documents.

### Health Tool Requests

- `BmiRequest`: `weight_kg`, `height_cm`
- `PbfRequest`: `pbf_percent`, `sex`
- `VisceralFatRequest`: `visceral_fat_level`
- `NutritionRequest`: `goal`, `weight_kg`, `activity_level`
- `TrainingRequest`: `goal`, `fitness_level`, `days_per_week`
- `SafetyRequest`: `question`, `conditions`

## 3. Nhóm Endpoint

### System

| Method | Path | Chức năng |
| --- | --- | --- |
| `GET` | `/` | Thông tin service |
| `GET` | `/health` | Kiểm tra cache, search, agent tools |

### Chat

| Method | Path | Chức năng |
| --- | --- | --- |
| `POST` | `/chat/complete` | Chat endpoint chính |
| `GET` | `/chat/complete/{task_id}` | Poll kết quả Celery async |
| `POST` | `/agent/answer` | Gọi agent trả lời trực tiếp |
| `GET` | `/agent/tools` | Xem danh sách tools |

### Retrieval và Indexing

| Method | Path | Chức năng |
| --- | --- | --- |
| `POST` | `/search` | Hybrid search |
| `POST` | `/collection/create` | Tạo Qdrant collection |
| `POST` | `/document/create` | Index một document |
| `POST` | `/documents/index` | Index nhiều documents |
| `POST` | `/data/import` | Alias import documents |

### Health Tools

| Method | Path | Chức năng |
| --- | --- | --- |
| `POST` | `/tools/bmi` | Tính BMI |
| `POST` | `/tools/pbf` | Đánh giá PBF |
| `POST` | `/tools/visceral-fat` | Đánh giá mỡ nội tạng |
| `POST` | `/tools/nutrition` | Gợi ý dinh dưỡng |
| `POST` | `/tools/training` | Gợi ý lịch tập |
| `POST` | `/tools/safety` | Kiểm tra cảnh báo y tế |

## 4. Ví Dụ Gọi API

### Chat

```bash
curl -X POST http://localhost:8000/chat/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "user_message": "PBF cao thì nên tập gì?",
    "sync_request": true
  }'
```

### Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "BMI trong báo cáo InBody nên đọc như thế nào?",
    "limit": 5,
    "use_rerank": true
  }'
```

### BMI Tool

```bash
curl -X POST http://localhost:8000/tools/bmi \
  -H "Content-Type: application/json" \
  -d '{"weight_kg": 70, "height_cm": 170}'
```

## 5. Cách FastAPI Xử Lý Lỗi

- Request thiếu field hoặc sai kiểu dữ liệu: FastAPI trả `422`.
- `user_id` hoặc `user_message` rỗng ở `/chat/complete`: backend trả `400`.
- Lỗi trong chat/index/search: backend log lỗi và trả `500`.
- Celery không khả dụng khi gọi async: backend trả `503`.

## 6. Chạy Service

Chạy bằng Docker:

```bash
cd backend
docker compose up --build
```

Chạy local:

```bash
cd backend
pip install -r requirements.txt
cd src
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```


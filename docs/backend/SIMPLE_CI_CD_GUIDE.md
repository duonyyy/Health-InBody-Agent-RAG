# Hướng Dẫn CI/CD Đơn Giản Cho Backend

Tài liệu này mô tả cách kiểm tra, build và deploy backend Health/InBody Agent RAG ở mức đơn giản, phù hợp cho demo hoặc môi trường tốt nghiệp.

## 1. Mục Tiêu

Pipeline tối thiểu nên đảm bảo:

1. Cài dependencies thành công.
2. Import source không lỗi.
3. Dataset schema hợp lệ.
4. Docker image build được.
5. API `/health` chạy được.
6. Backend kết nối được Qdrant, PostgreSQL, Valkey và embed_serving khi cần.

## 2. Kiểm Tra Local Trước Khi Deploy

Chạy từ thư mục gốc project:

```bash
python backend/src/import_data.py --dry-run
```

Kỳ vọng:

```json
{
  "status": true,
  "skipped_docs": 0,
  "error_count": 0
}
```

Chạy backend local:

```bash
cd backend
pip install -r requirements.txt
cd src
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

Kiểm tra:

```bash
curl http://localhost:8000/health
```

## 3. Build Và Chạy Docker Compose

Chạy từ thư mục `backend/`:

```bash
docker compose up --build
```

Các service chính:

- `chatbot-api`: FastAPI backend.
- `chatbot-worker`: Celery worker.
- `valkey-db`: Redis-compatible broker/result backend.
- `qdrant-db`: vector database.
- `postgres-db`: relational database.

Kiểm tra API:

```bash
curl http://localhost:8000/health
```

## 4. embed_serving

Embedding service nằm ở thư mục:

```text
embed_serving/
```

Nếu chạy bằng compose riêng, service expose:

```text
http://localhost:5001
```

Backend mặc định gọi:

```env
CUSTOM_EMBEDDING_API_URL=http://host.docker.internal:5001
```

Nếu đưa `embedding-api` vào cùng Docker network với backend, đổi thành:

```env
CUSTOM_EMBEDDING_API_URL=http://embedding-api:5000
```

Kiểm tra embedding service:

```bash
curl http://localhost:5001/health
```

## 5. Biến Môi Trường Cần Có

File `.env` trong `backend/` nên có các biến phù hợp:

```env
QDRANT_URL=http://qdrant-db:6333
QDRANT_COLLECTION_NAME=nmk_chatbot_active
VECTOR_SIZE=1024
CUSTOM_EMBEDDING_API_URL=http://host.docker.internal:5001
DATABASE_URL=postgresql+psycopg2://health_user:change-me@postgres-db:5432/health_inbody
LLM_PROVIDER=none
```

Nếu dùng Ollama:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:3b
```

Nếu dùng OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

## 6. Import Dataset Sau Khi Deploy

Tạo dataset:

```bash
python data_pipeline/utils/build_embedding_dataset.py
```

Import trực tiếp:

```bash
python backend/src/import_data.py
```

Hoặc import qua API:

```bash
python data_pipeline/utils/index_mvp_dataset.py --batch-size 50
```

## 7. Checklist CI Tối Thiểu

```bash
python backend/src/import_data.py --dry-run
docker compose -f backend/docker-compose.yml config
docker compose -f backend/docker-compose.yml build
```

Nếu có môi trường integration:

```bash
docker compose -f backend/docker-compose.yml up -d
curl http://localhost:8000/health
```

## 8. Checklist Trước Khi Demo

- Backend `/health` trả `status=healthy`.
- Qdrant collection `nmk_chatbot_collection` có points.
- `embed_serving /health` trả `model_loaded=true`.
- `/search` trả kết quả cho câu hỏi về BMI/PBF/mỡ nội tạng.
- `/chat/complete` trả câu trả lời tiếng Việt.
- LLM provider đã cấu hình hoặc biết rõ đang chạy `LLM_PROVIDER=none`.
- Không còn file cache như `__pycache__`, `.pyc`.

## 9. Rollback Đơn Giản

Với demo local, rollback thường là:

```bash
docker compose down
docker compose up --build
```

Nếu collection Qdrant sai dimension, cần tạo lại collection với `VECTOR_SIZE=1024` và import dataset lại.

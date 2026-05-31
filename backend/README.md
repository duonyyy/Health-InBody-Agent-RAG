# Backend - Health/InBody Agent RAG

Backend la dich vu FastAPI cho he thong Health/InBody Agent RAG. Service nay phu trach nhan request chat, dieu phoi route cau hoi, truy xuat tai lieu tu Qdrant/BM25, goi LLM sinh cau tra loi, va cung cap cac health tools co ban nhu tinh BMI, danh gia PBF, mo noi tang, dinh duong va lich tap.

> Luu y y te: he thong chi cung cap thong tin tham khao ve suc khoe, InBody, dinh duong va tap luyen. He thong khong chan doan benh, khong ke don thuoc va khong thay the bac si.

## 1. Thanh Phan Chinh

```text
backend/
├── src/
│   ├── app.py               # FastAPI routes
│   ├── agent.py             # Agent orchestration cho health tools/RAG
│   ├── brain.py             # LLM provider, prompt, route detection, embedding wrapper
│   ├── custom_embedding.py  # Client goi embed_serving API
│   ├── search.py            # Hybrid search: BM25 + vector search + rerank
│   ├── vectorize.py         # Qdrant collection/search/upsert
│   ├── splitter.py          # Tach document thanh chunks
│   ├── tasks.py             # Celery tasks va indexing documents
│   ├── health_tools.py      # BMI, PBF, visceral fat, nutrition, training, safety
│   ├── import_data.py       # Import corpus tu data_pipeline vao Qdrant
│   ├── database.py          # SQLAlchemy session/engine
│   └── models.py            # ORM models
├── data/
├── Dockerfile
├── docker-compose.yml
├── import_data.sh
└── requirements.txt
```

## 2. Luong Hoat Dong

### Chat RAG

1. Frontend goi `POST /chat/complete` hoac `POST /agent/answer`.
2. Backend phan loai route: `health_rag`, `agent_tools`, `web_search`, `general_chat`.
3. Voi `health_rag`, backend rewrite query, chay hybrid search, rerank documents.
4. Backend goi LLM provider de sinh cau tra loi tieng Viet co guardrail y te.
5. Ket qua tra ve frontend.

### Index Tai Lieu

1. `data_pipeline` tao file:
   `data_pipeline/dataset/processed/embedding_documents.jsonl`
2. Backend tach moi document thanh chunks.
3. Backend goi `embed_serving` qua `/embed` de tao vector.
4. Vector va payload duoc upsert vao Qdrant collection `nmk_chatbot_collection`.
5. BM25 index duoc khoi tao tu documents da index.

## 3. Bien Moi Truong

Backend doc cau hinh tu `.env` va `docker-compose.yml`.

| Bien | Mac dinh | Y nghia |
| --- | --- | --- |
| `QDRANT_URL` | `http://qdrant-db:6333` | URL Qdrant trong Docker network |
| `QDRANT_COLLECTION_NAME` | `nmk_chatbot_collection` | Collection dung cho RAG |
| `VECTOR_SIZE` | `1024` | Kich thuoc vector embedding, phu hop BGE-M3 |
| `CUSTOM_EMBEDDING_API_URL` | `http://host.docker.internal:5001` | URL cua embed_serving |
| `DATABASE_URL` | `postgresql+psycopg2://health_user:health_password@postgres-db:5432/health_inbody` | PostgreSQL connection string |
| `LLM_PROVIDER` | `ollama` trong code, compose dang set fallback `none` | Provider LLM: `ollama`, `openai`, `custom`, `none` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model Ollama |
| `OPENAI_API_KEY` | empty | Can neu dung OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model OpenAI |
| `TAVILY_API_KEY` | empty | Can neu dung web search |

Neu chay `embed_serving` bang compose rieng nhu hien tai, backend se goi qua:

```env
CUSTOM_EMBEDDING_API_URL=http://host.docker.internal:5001
```

Neu dua `embedding-api` vao cung Docker network voi backend, nen doi thanh:

```env
CUSTOM_EMBEDDING_API_URL=http://embedding-api:5000
```

## 4. Chay Bang Docker Compose

Chay tu thu muc `backend/`:

```bash
docker compose up --build
```

Service mac dinh:

- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Qdrant: `http://localhost:6333`
- PostgreSQL: `localhost:5432`
- Valkey/Redis: `localhost:6379`

Kiem tra health:

```bash
curl http://localhost:8000/health
```

## 5. Chay Local Khong Docker

Chay tu thu muc `backend/`:

```bash
pip install -r requirements.txt
cd src
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Can dam bao cac service phu tro da chay:

- Qdrant
- PostgreSQL
- Valkey/Redis neu dung Celery
- `embed_serving` neu can vector search/indexing
- LLM provider neu can chat generation

## 6. Import Dataset Vao Qdrant

### Cach 1: Import truc tiep bang backend script

Chay tu thu muc goc project:

```bash
python backend/src/import_data.py --dry-run
```

Neu dry-run hop le, chay import that:

```bash
python backend/src/import_data.py
```

Mac dinh script doc:

```text
data_pipeline/dataset/processed/embedding_documents.jsonl
```

### Cach 2: Gui qua API `/documents/index`

Chay tu thu muc goc project:

```bash
python data_pipeline/utils/index_mvp_dataset.py --batch-size 50
```

Ten script con chu `mvp` de tuong thich tai lieu cu, nhung input mac dinh hien tai la `embedding_documents.jsonl`.

## 7. Endpoint Chinh

### System

| Method | Path | Mo ta |
| --- | --- | --- |
| `GET` | `/` | Thong tin service |
| `GET` | `/health` | Health check cache, search, agent tools |

### Chat va Agent

| Method | Path | Mo ta |
| --- | --- | --- |
| `POST` | `/chat/complete` | Chat endpoint chinh |
| `GET` | `/chat/complete/{task_id}` | Lay ket qua Celery async |
| `POST` | `/agent/answer` | Goi agent tra loi truc tiep |
| `GET` | `/agent/tools` | Liet ke health tools |

Vi du:

```bash
curl -X POST http://localhost:8000/chat/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "user_message": "BMI va PBF khac nhau nhu the nao?",
    "sync_request": true
  }'
```

### Retrieval va Indexing

| Method | Path | Mo ta |
| --- | --- | --- |
| `POST` | `/search` | Hybrid search tren corpus Health/InBody |
| `POST` | `/collection/create` | Tao Qdrant collection |
| `POST` | `/document/create` | Index mot document |
| `POST` | `/documents/index` | Index nhieu documents |
| `POST` | `/data/import` | Alias import documents |

Vi du search:

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mo noi tang cao nen lam gi",
    "limit": 5,
    "use_rerank": true
  }'
```

### Health Tools

| Method | Path | Mo ta |
| --- | --- | --- |
| `POST` | `/tools/bmi` | Tinh BMI |
| `POST` | `/tools/pbf` | Danh gia phan tram mo co the |
| `POST` | `/tools/visceral-fat` | Danh gia mo noi tang |
| `POST` | `/tools/nutrition` | Goi y muc tieu dinh duong |
| `POST` | `/tools/training` | Goi y lich tap |
| `POST` | `/tools/safety` | Kiem tra canh bao y te |

Vi du BMI:

```bash
curl -X POST http://localhost:8000/tools/bmi \
  -H "Content-Type: application/json" \
  -d '{"weight_kg": 70, "height_cm": 170}'
```

## 8. Contract Voi embed_serving

Backend goi:

```http
POST /embed
Content-Type: application/json

{
  "texts": ["noi dung can embedding"],
  "batch_size": 32
}
```

`embed_serving` tra ve:

```json
{
  "embeddings": [[0.1, 0.2]],
  "embedding_dim": 1024,
  "num_texts": 1,
  "inference_time": 0.123
}
```

Backend chi can field `embeddings`. `embedding_dim` nen trung voi `VECTOR_SIZE` va Qdrant collection size.

## 9. Ghi Chu Van Hanh

- Neu `/search` khong tra vector results, kiem tra `embed_serving`, `CUSTOM_EMBEDDING_API_URL` va Qdrant collection.
- Neu chat loi LLM, kiem tra `LLM_PROVIDER` va endpoint/API key tuong ung.
- Neu import dataset bi loi dimension, xoa/tai tao collection Qdrant voi dung `VECTOR_SIZE=1024`.
- Neu BM25 chua co data sau khi restart, co the goi import/index lai hoac de backend load payload tu Qdrant khi search.
- File `data_pipeline/dataset/processed/embedding_documents.jsonl` la corpus chinh; khong dung file `mvp_embedding_documents.jsonl` cu.


# Giải Thích Celery Tasks Trong Backend

File `backend/src/tasks.py` chứa các hàm xử lý nền và các hàm pipeline chính cho chatbot Health/InBody Agent RAG. Trong môi trường Docker, Celery worker chạy riêng với broker/result backend là Valkey/Redis.

## 1. Celery Dùng Để Làm Gì?

Celery giúp xử lý các tác vụ tốn thời gian mà không khóa request FastAPI:

- Sinh câu trả lời chat bất đồng bộ.
- Truy xuất RAG nhiều bước.
- Index tài liệu vào Qdrant.
- Gọi embedding service cho nhiều chunks.

Trong compose hiện tại:

```text
chatbot-api     -> FastAPI service
chatbot-worker  -> Celery worker
valkey-db       -> broker/result backend
qdrant-db       -> vector database
postgres-db     -> relational database
```

## 2. Các Hàm Quan Trọng

### `follow_up_question(history, question)`

Viết lại câu hỏi follow-up thành câu hỏi độc lập bằng logic trong `brain.detect_user_intent`.

Ví dụ:

```text
History: "PBF của tôi là 28%"
Question: "Vậy có cao không?"
Output: "PBF 28% có cao không?"
```

### `retrieve_with_hybrid_search(queries, top_k=5)`

Nhận nhiều biến thể query, gọi `hybrid_search()` cho từng query, khử trùng lặp tài liệu và trả về danh sách context ứng viên.

### `bot_rag_answer_message(history, question)`

Pipeline RAG chính:

1. Viết lại follow-up question.
2. Tạo nhiều query bằng `rewrite_query_to_multi_queries`.
3. Gọi hybrid search.
4. Rerank documents.
5. Gọi `generate_health_answer` để sinh câu trả lời.

### `bot_route_answer_message(history, question)`

Chọn route xử lý:

- `health_rag`: gọi `bot_rag_answer_message`.
- `agent_tools`: gọi tool tính toán/đánh giá sức khỏe.
- `web_search`: gọi Tavily rồi LLM tổng hợp.
- `general_chat`: trả lời hội thoại thông thường.

### `index_document_v2(id, question, content, collection_name, metadata)`

Index một document:

1. Ghép `question` và `content`.
2. Tách chunk bằng `splitter.split_document`.
3. Gọi `brain.get_embedding`, thực chất gọi `custom_embedding`.
4. Tạo point ID ổn định bằng UUID v5.
5. Upsert vào Qdrant qua `vectorize.add_vector`.

### `index_health_documents(documents, collection_name)`

Index nhiều documents từ API `/documents/index` hoặc `/data/import`.

Sau khi index, hàm gọi `initialize_search_index()` để khởi tạo BM25 in-memory cho batch vừa gửi.

### `llm_handle_message(bot_id, user_id, question)`

Handler chat chính cho `/chat/complete` khi chạy sync hoặc async. Hiện tại DB conversation còn tối giản, hàm trả về response trực tiếp:

```json
{
  "role": "assistant",
  "content": "..."
}
```

## 3. Luồng Chat Đồng Bộ

Khi client gửi:

```http
POST /chat/complete
```

với `sync_request=true`, FastAPI gọi trực tiếp:

```text
llm_handle_message -> bot_route_answer_message -> route handler
```

Đây là đường chạy thuận tiện cho demo và kiểm thử.

## 4. Luồng Chat Bất Đồng Bộ

Khi `sync_request=false`, FastAPI tạo Celery task:

```text
llm_handle_message.delay(...)
```

Client nhận `task_id`, sau đó poll:

```http
GET /chat/complete/{task_id}
```

## 5. Luồng Index Dataset

Dataset chính được tạo bởi data pipeline:

```text
data_pipeline/dataset/processed/embedding_documents.jsonl
```

Có 2 cách index:

```bash
python backend/src/import_data.py
```

hoặc:

```bash
python data_pipeline/utils/index_mvp_dataset.py --batch-size 50
```

Tên `index_mvp_dataset.py` được giữ để tương thích tài liệu cũ, nhưng input mặc định hiện tại là `embedding_documents.jsonl`.

## 6. Lưu Ý Vận Hành

- Nếu worker không chạy, endpoint async sẽ không xử lý task.
- Nếu `embed_serving` không chạy, indexing và vector search sẽ lỗi hoặc trả rỗng.
- Nếu Qdrant collection sai `VECTOR_SIZE`, cần tạo lại collection đúng dimension embedding.
- Nếu restart backend, BM25 in-memory có thể cần khởi tạo lại từ Qdrant hoặc index lại batch documents.


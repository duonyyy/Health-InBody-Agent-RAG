# Celery Tasks Explained

File `backend/src/tasks.py` chứa các task nền cho indexing và chat async. Sau khi chuyển sang Multi-Agent RAG MVP, handler chat async dùng cùng entrypoint với sync API để tránh lệch logic.

## 1. Indexing tasks

### `index_document_v2(...)`

- Tách tài liệu thành chunks.
- Gọi embedding API qua `get_embedding`.
- Upsert vector vào Qdrant.

### `index_health_documents(...)`

- Index nhiều tài liệu Health/InBody.
- Chuẩn hóa payload cho search.
- Khởi tạo BM25 index bằng `initialize_search_index`.

## 2. Chat task hiện tại

### `llm_handle_message(bot_id, user_id, question)`

Handler chính cho `/chat/complete` khi chạy async. Hiện tại hàm này gọi:

```python
multi_agent_handle(question, history=[])
```

Kết quả trả về có dạng:

```json
{
  "role": "assistant",
  "content": "...",
  "agent_trace": [],
  "selected_agents": [],
  "tool_results": [],
  "retrieved_docs": [],
  "safety_result": {},
  "errors": []
}
```

## 3. Các hàm route cũ

Các hàm như `bot_route_answer_message` và `bot_rag_answer_message` vẫn còn để tương thích/đối chiếu, nhưng không còn là flow chính của chat MVP. Flow chính là `agents.multi_agent_handle`.

## 4. Async flow

```text
POST /chat/complete sync_request=false
  -> llm_handle_message.delay(...)
  -> multi_agent_handle(...)
  -> GET /chat/complete/{task_id}
  -> task_result.content + task_result.agent_trace
```

## 5. Lưu ý vận hành

- Nếu Celery worker không chạy, dùng `sync_request=true`.
- Nếu LLM provider bị tắt (`LLM_PROVIDER=none`), ResponseComposerAgent sẽ trả fallback answer từ tool/RAG/safety state.
- Async hiện chưa truyền history vào task; sync chat từ frontend có truyền history.

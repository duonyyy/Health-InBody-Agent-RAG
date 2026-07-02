# FastAPI Concepts Explained

File `backend/src/app.py` là entrypoint FastAPI của Health/InBody Multi-Agent RAG MVP. File này định nghĩa request schema, endpoint chat, agent capability, search, indexing, summarization và health tools.

## 1. App metadata

```python
app = FastAPI(
    title="Health/InBody Agent RAG Backend",
    version="1.0.0-beta",
)
```

Tên app vẫn giữ `Agent RAG Backend` để tương thích tài liệu cũ, nhưng flow chat chính hiện là Multi-Agent RAG MVP.

## 2. Chat request

`CompleteRequest` dùng cho `/chat/complete`:

```python
class CompleteRequest(BaseModel):
    bot_id: Optional[str] = "health-inbody-agent"
    user_id: str
    user_message: str
    history: Optional[List[Dict[str, str]]] = None
    sync_request: Optional[bool] = True
```

## 3. Chat response mới

`POST /chat/complete` với `sync_request=true` gọi:

```python
multi_agent_handle(data.user_message, history=data.history)
```

Response:

```json
{
  "response": {
    "role": "assistant",
    "content": "...",
    "agent_trace": [
      {
        "agent": "SupervisorAgent",
        "action": "select_agents",
        "status": "success",
        "summary": "Selected agents: InBodyAgent, RAGAgent"
      }
    ],
    "selected_agents": [],
    "tool_results": [],
    "retrieved_docs": [],
    "safety_result": {},
    "errors": []
  }
}
```

## 4. Endpoint chính

| Method | Path | Mô tả |
| --- | --- | --- |
| `GET` | `/health` | Health check và multi-agent summary |
| `POST` | `/chat/complete` | Chat endpoint chính |
| `GET` | `/chat/complete/{task_id}` | Poll kết quả Celery async |
| `POST` | `/agent/answer` | Gọi multi-agent trực tiếp |
| `GET` | `/agent/tools` | Liệt kê agent capabilities và trace schema |
| `POST` | `/search` | Hybrid search trên corpus |
| `POST` | `/tools/bmi` | Debug endpoint tính BMI |
| `POST` | `/tools/pbf` | Debug endpoint đánh giá PBF |
| `POST` | `/tools/visceral-fat` | Debug endpoint đánh giá mỡ nội tạng |
| `POST` | `/tools/nutrition` | Debug endpoint dinh dưỡng |
| `POST` | `/tools/training` | Debug endpoint lịch tập |
| `POST` | `/tools/safety` | Debug endpoint safety |

## 5. Ví dụ request

```bash
curl -X POST http://localhost:8000/chat/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "user_message": "Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng level 12. Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi/tuần?",
    "sync_request": true
  }'
```

## 6. Lưu ý

- Người dùng cuối nên đi qua `/chat/complete`, không cần gọi `/tools/...` trực tiếp.
- `/tools/...` được giữ để dev/debug và test từng tool.
- Backend hiện chưa có endpoint upload/parse ảnh hoặc PDF InBody.

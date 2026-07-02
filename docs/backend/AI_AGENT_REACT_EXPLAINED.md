# Multi-Agent RAG MVP Explained

Tài liệu này mô tả phần agent backend hiện tại của dự án Health/InBody Multi-Agent RAG MVP. Backend không còn là một router đơn chọn đúng một route, mà dùng một graph nhiều agent để xử lý câu hỏi phức hợp.

## 1. File chính

- `backend/src/agents/graph.py`: LangGraph Multi-Agent RAG MVP, entrypoint `multi_agent_handle`.
- `backend/src/agents/state.py`: shared state và trace helpers.
- `backend/src/agents/parsing.py`: helper trích xuất cân nặng, chiều cao, PBF, mỡ nội tạng, mục tiêu.
- `backend/src/app.py`: FastAPI endpoint gọi multi-agent handler.
- `backend/src/agent.py`: wrapper tương thích ngược cho code cũ.

## 2. Agent trong MVP

| Agent | Vai trò |
| --- | --- |
| `QuestionNormalizerAgent` | Viết lại follow-up question thành câu hỏi độc lập |
| `SupervisorAgent` | Chọn một hoặc nhiều agent chuyên trách |
| `InBodyAgent` | Tính BMI, đánh giá PBF và mỡ nội tạng |
| `RAGAgent` | Rewrite query, hybrid search, rerank tài liệu |
| `NutritionAgent` | Gợi ý protein và calorie strategy |
| `TrainingAgent` | Gợi ý lịch tập cơ bản |
| `WebSearchAgent` | Tìm thông tin mới khi câu hỏi cần tính thời sự |
| `SafetyAgent` | Luôn chạy guardrail y tế |
| `ResponseComposerAgent` | Tổng hợp câu trả lời cuối |

## 3. Shared State

Các agent cùng đọc/ghi vào state:

```python
{
    "question": "...",
    "history": [],
    "standalone_question": "...",
    "selected_agents": [],
    "tool_results": [],
    "retrieved_docs": [],
    "safety_result": {},
    "agent_trace": [],
    "final_answer": ""
}
```

## 4. Luồng xử lý

```text
normalize_question
  -> supervisor
  -> inbody_agent
  -> nutrition_agent
  -> training_agent
  -> rag_agent
  -> web_search_agent
  -> general_chat_agent
  -> safety_agent
  -> response_composer
```

Các node domain agent chỉ thực sự xử lý khi tên agent có trong `selected_agents`. Cách này giữ graph đơn giản nhưng vẫn cho phép một câu hỏi gọi nhiều agent.

## 5. Agent Trace

Mỗi bước ghi trace dạng:

```json
{
  "agent": "InBodyAgent",
  "action": "evaluate_inbody_metrics",
  "status": "success",
  "summary": "Evaluated BMI, PBF, visceral fat."
}
```

Frontend hiển thị trace trong expander `Agent trace` để demo và debug.

## 6. Ví dụ demo

Input:

```text
Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng level 12. Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi/tuần?
```

Expected selected agents:

```text
InBodyAgent, NutritionAgent, TrainingAgent, RAGAgent
```

SafetyAgent và ResponseComposerAgent luôn chạy sau đó.

## 7. Giới hạn MVP

- Chưa có upload/parse ảnh hoặc PDF InBody.
- Supervisor MVP dùng keyword + route fallback để ổn định demo, chưa phải planner phức tạp.
- Các endpoint `/tools/...` vẫn tồn tại để dev/debug, nhưng flow người dùng chính là `/chat/complete`.

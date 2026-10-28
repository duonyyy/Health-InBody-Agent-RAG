# Multi-Agent RAG MVP Explained

Tài liệu này mô tả chi tiết kiến trúc điều phối Agent Backend của dự án **Health/InBody Multi-Agent RAG**. Backend không dùng một router đơn giản chỉ chọn duy nhất một route, mà sử dụng một Graph trạng thái (LangGraph) để phối hợp linh hoạt nhiều agent chuyên trách, đồng thời tích hợp các cơ chế Fast-path quyết định (deterministic) để đảm bảo an toàn và tối ưu tài nguyên.

---

## 1. Cấu Trúc File Chính

- `backend/src/agents/graph.py`: LangGraph Multi-Agent RAG, entrypoint `multi_agent_handle`.
- `backend/src/agents/state.py`: Định nghĩa `AgentState` (shared state) và các helper ghi trace, evidence.
- `backend/src/agents/parsing.py`: Helper trích xuất thực thể (cân nặng, chiều cao, PBF, mỡ nội tạng, mục tiêu) bằng regex chuẩn hóa.
- `backend/src/api/app.py`: FastAPI application cung cấp contract `/agent/answer` và `/chat/complete`.
- `backend/src/health/tools.py`: Các hàm tính toán chỉ số (BMI, PBF, mỡ nội tạng), dinh dưỡng, lịch tập và kiểm tra quy tắc an toàn y tế.

---

## 2. Danh Sách Agent Chuyên Trách

| Agent | Vai trò chính |
| --- | --- |
| `QuestionNormalizerAgent` | Chuẩn hóa câu hỏi theo ngữ cảnh lịch sử hội thoại thành câu độc lập |
| `SupervisorAgent` | Phân tích ý định và chọn danh sách các agent phù hợp cần kích hoạt |
| `InBodyAgent` | Tính toán chỉ số BMI, đánh giá tỷ lệ mỡ (PBF) và cấp độ mỡ nội tạng |
| `RAGAgent` | Tái cấu trúc truy vấn, thực hiện Hybrid Search (Vector + BM25) trên corpus y tế |
| `NutritionAgent` | Tính toán mục tiêu calo và phân bổ macro/protein theo thể trạng |
| `TrainingAgent` | Đề xuất lịch tập luyện kháng lực và cardio theo số buổi/tuần |
| `WebSearchAgent` | Tìm kiếm dữ liệu mới qua Tavily khi câu hỏi mang tính thời sự hoặc nghiên cứu mới |
| `SafetyAgent` | Áp dụng guardrail an toàn y tế bắt buộc, lọc bỏ lời khuyên cực đoan |
| `ResponseComposerAgent` | Tổng hợp thông tin từ các agent thành câu trả lời mạch lạc, kèm trích dẫn |

---

## 3. Cơ Chế Fast-Path Tốc Độ Cao (P0)

Để tiết kiệm chi phí tính toán và bảo vệ an toàn y tế tuyệt đối, hệ thống có 2 cơ chế Fast-Path bỏ qua LLM/RAG:

1.  **Deterministic Safety Pre-Check:**
    *   Chạy kiểm tra quy tắc triệu chứng khẩn cấp (đau ngực, khó thở, ngất xỉu, v.v.) **ngay trước khi vào Graph**.
    *   Nếu phát hiện nguy cơ `urgent`, trả về cảnh báo cố định lập tức trong **~10–40 ms**, không gọi LLM, Qdrant hay Web Search.
2.  **BMI Tool Fast-Path:**
    *   Nếu câu hỏi chỉ đơn thuần yêu cầu tính toán BMI từ chiều cao & cân nặng hợp lệ, hệ thống tính toán bằng pure-Python tool và trả lời trong **~15 ms**.

---

## 4. Shared State (`AgentState`)

Tất cả các node trong Graph cùng chia sẻ và cập nhật trạng thái chung:

```python
{
    "question": "...",
    "history": [],
    "standalone_question": "...",
    "selected_agents": [],
    "tool_results": [],
    "retrieved_docs": [],
    "evidence": [],                # Danh sách citations đã được map vào tài liệu thực tế
    "evidence_status": "supported",# supported | partial | insufficient | not_required
    "limitations": [],             # Giới hạn dữ liệu/khuyến cáo
    "safety_result": {},
    "personalization_used": {},    # Dữ liệu profile/measurement đã xác nhận
    "agent_trace": [],             # Dấu vết thực thi của từng agent
    "final_answer": "",
    "errors": []
}
```

---

## 5. Luồng Xử Lý Trong Graph

```text
[Input Request]
      ↓
[Safety Pre-Check] ──(urgent)──> [Return Emergency Fast-Path (~40ms)]
      ↓ (safe)
[BMI Check] ──────(only BMI)───> [Return BMI Fast-Path (~15ms)]
      ↓ (normal)
normalize_question
      ↓
supervisor (chọn các agent)
      ↓
┌────────────────────────────────────────────────────────┐
│  Các domain agent (chạy khi có trong selected_agents): │
│  ├─ inbody_agent                                       │
│  ├─ nutrition_agent                                    │
│  ├─ training_agent                                     │
│  ├─ rag_agent                                          │
│  ├─ web_search_agent                                   │
│  └─ general_chat_agent                                 │
└────────────────────────────────────────────────────────┘
      ↓
safety_agent (chạy guardrail kiểm tra chéo)
      ↓
response_composer (tổng hợp câu trả lời & gắn citations)
      ↓
[Output Contract]
```

---

## 6. Minh Chứng Thực Thi (`agent_trace`)

Mỗi node ghi lại vết hoạt động để giao diện Streamlit hiển thị trực quan cho người dùng và phục vụ chấm điểm đồ án:

```json
{
  "agent": "InBodyAgent",
  "action": "evaluate_inbody_metrics",
  "status": "success",
  "summary": "Evaluated BMI, PBF, visceral fat."
}
```

---

## 7. Giới Hạn Hiện Tại (Roadmap)

- OCR đọc ảnh/PDF kết quả InBody đang thuộc lộ trình P2 (hiện tại người dùng nhập số liệu qua chat).
- Metadata nguồn corpus đang ở mức seed/curated công khai, chưa qua thẩm định y khoa chính thức.

# Giải Thích Tavily Search Trong Dự Án

Tavily được dùng cho route `web_search` trong Health/InBody Agent RAG. Route này chỉ nên dùng khi câu hỏi cần thông tin mới, nghiên cứu gần đây, tin tức hoặc dữ liệu thời sự mà corpus nội bộ có thể chưa cập nhật.

## 1. Khi Nào Dùng Tavily?

Ví dụ nên dùng web search:

```text
Có nghiên cứu mới nhất năm 2026 về mỡ nội tạng không?
```

```text
Khuyến nghị gần đây về protein cho người tập kháng lực là gì?
```

Ví dụ không cần Tavily:

```text
BMI là gì?
```

```text
PBF cao thì nên hiểu thế nào trong báo cáo InBody?
```

Những câu hỏi cơ bản nên dùng `health_rag` với corpus nội bộ.

## 2. File Liên Quan

- `backend/src/tavily_tool.py`: wrapper gọi Tavily API.
- `backend/src/brain.py`: phát hiện route `web_search`.
- `backend/src/tasks.py`: gọi `tavily_search_health()` rồi đưa kết quả cho LLM tổng hợp.

## 3. Luồng Xử Lý

```text
user question
  -> detect_route
  -> web_search
  -> follow_up_question
  -> tavily_search_health
  -> openai_chat_complete / configured LLM
  -> final answer
```

Câu trả lời cuối phải:

- Tổng hợp ngắn gọn.
- Nêu rõ đây là thông tin tham khảo.
- Không chẩn đoán hoặc kê đơn.
- Khuyên gặp chuyên gia y tế khi có triệu chứng nguy hiểm hoặc bệnh nền.
- Có nguồn nếu kết quả Tavily cung cấp.

## 4. Cấu Hình

Cần biến môi trường:

```env
TAVILY_API_KEY=...
```

Nếu không có key hoặc API lỗi, backend nên log lỗi và tránh làm hỏng toàn bộ service.

## 5. Quan Hệ Với RAG Nội Bộ

Tavily không thay thế corpus chính:

```text
data_pipeline/dataset/processed/embedding_documents.jsonl
```

RAG nội bộ vẫn là nguồn chính cho:

- Giải thích chỉ số InBody.
- Dinh dưỡng và tập luyện cơ bản.
- Guardrail y tế.
- Các câu hỏi không cần thông tin thời sự.

Tavily là nguồn bổ sung khi người dùng hỏi "mới nhất", "gần đây", "năm 2026", "vừa công bố" hoặc nội dung tương tự.

## 6. Ví Dụ Câu Hỏi

```text
Nghiên cứu mới nhất về mỡ nội tạng và nguy cơ tim mạch nói gì?
```

Route dự kiến:

```text
web_search
```

Kết quả mong muốn:

- Tóm tắt 2-4 ý chính.
- Nhắc người dùng không tự chẩn đoán.
- Khuyến nghị gặp bác sĩ nếu có nguy cơ hoặc triệu chứng.


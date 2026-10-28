# Tavily Search & WebSearchAgent

Tavily Search API được tích hợp vào hệ thống **Health/InBody Multi-Agent RAG** thông qua module `backend/src/integrations/tavily.py`, phục vụ riêng cho tác tử `WebSearchAgent`.

Agent này được thiết kế để mở rộng tri thức ra ngoài phạm vi kho tài liệu nội bộ khi người dùng đặt các câu hỏi mang tính thời sự, nghiên cứu y học mới công bố hoặc các hướng dẫn sức khỏe gần đây.

---

## 1. Dấu Hiệu Kích Hoạt `WebSearchAgent`

Bộ phân loại của `SupervisorAgent` sẽ cân nhắc chọn `WebSearchAgent` khi phát hiện các đặc trưng:
- Từ khóa thời gian: *"mới nhất"*, *"gần đây"*, *"hôm nay"*, *"năm 2026"*, *"vừa công bố"*.
- Hỏi về xu hướng hoặc nghiên cứu mới: *"nghiên cứu mới về mối liên hệ giữa mỡ nội tạng và tim mạch"*, *"hướng dẫn mới của WHO về tiêu thụ đường"*.

---

## 2. Luồng Điều Phối Trong Multi-Agent Graph

```text
[User Query]
     ↓
[SupervisorAgent]
     ↓
┌──────────────────────────────────────┐
│  Kích hoạt WebSearchAgent            │
│  (Kết hợp cùng InBodyAgent nếu có số)│
└──────────────────────────────────────┘
     ↓
[Tavily Search API Call] ──> [Trích xuất tóm tắt và nguồn web uy tín]
     ↓
[SafetyAgent] ─────────────> [Áp đặt rào cản an toàn y tế bắt buộc]
     ↓
[ResponseComposerAgent] ───> [Tổng hợp thông tin kèm liên kết nguồn web]
```

---

## 3. Cấu Trúc File Liên Quan

- `backend/src/integrations/tavily.py`: Wrapper xử lý kết nối HTTP tới API Tavily, lọc kết quả và xử lý ngoại lệ timeout.
- `backend/src/agents/graph.py`: Định nghĩa node `web_search_agent` trong đồ thị LangGraph.

---

## 4. Nguyên Tắc An Toàn (Safety Guardrails)

Dữ liệu thu thập từ Internet luôn có tính biến động và rủi ro:
1.  **Không tin cậy mù quáng:** `SafetyAgent` luôn chạy sau `WebSearchAgent` để kiểm duyệt nội dung, ngăn chặn các trào lưu ăn kiêng cực đoan hoặc lời khuyên dùng thuốc tự ý.
2.  **Giới hạn trách nhiệm:** Mọi câu trả lời sử dụng dữ liệu web đều phải đi kèm khuyến cáo: *"Thông tin được tổng hợp từ nguồn tham khảo công khai, người dùng cần tham vấn ý kiến bác sĩ chuyên khoa trước khi áp dụng."*

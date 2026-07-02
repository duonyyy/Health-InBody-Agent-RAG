# Tavily Search Explained

Tavily được dùng bởi `WebSearchAgent` trong Health/InBody Multi-Agent RAG MVP. Agent này chỉ nên chạy khi câu hỏi cần thông tin mới, nghiên cứu gần đây, tin tức hoặc dữ liệu thời sự mà corpus nội bộ có thể chưa cập nhật.

## 1. Khi nào dùng WebSearchAgent

Các dấu hiệu:

- "mới nhất"
- "gần đây"
- "hôm nay"
- "năm 2026"
- "vừa công bố"
- câu hỏi về nghiên cứu hoặc khuyến nghị mới

Ví dụ:

```text
Nghiên cứu mới nhất về mỡ nội tạng và nguy cơ tim mạch nói gì?
```

## 2. Flow trong multi-agent

```text
SupervisorAgent
  -> WebSearchAgent
  -> SafetyAgent
  -> ResponseComposerAgent
```

Nếu câu hỏi vừa có chỉ số cá nhân vừa cần thông tin mới, SupervisorAgent có thể chọn thêm agent khác:

```text
SupervisorAgent
  -> InBodyAgent
  -> WebSearchAgent
  -> SafetyAgent
  -> ResponseComposerAgent
```

## 3. File liên quan

- `backend/src/tavily_tool.py`: wrapper Tavily.
- `backend/src/agents/graph.py`: `web_search_agent`.
- `backend/src/brain.py`: vẫn giữ route detection fallback cho tương thích.

## 4. Safety

Thông tin web chỉ dùng ở mức tham khảo. ResponseComposerAgent vẫn phải:

- Không chẩn đoán bệnh.
- Không kê đơn.
- Khuyến nghị gặp bác sĩ khi có triệu chứng nguy hiểm hoặc bệnh nền phức tạp.

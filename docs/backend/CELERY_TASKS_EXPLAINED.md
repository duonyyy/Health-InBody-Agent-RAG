# Celery Tasks & Async Processing

File `backend/src/jobs/tasks.py` chịu trách nhiệm quản lý các tác vụ nền bất đồng bộ (Background Tasks) bằng Celery và Valkey (Redis-compatible broker) nhằm giải phóng luồng chính của FastAPI khi xử lý các công việc tốn nhiều thời gian như nạp tập tài liệu lớn (bulk indexing) hoặc xử lý hàng đợi tin nhắn.

---

## 1. Các Tác Vụ Indexing Dữ Liệu

### 1.1 `index_document_v2(...)`
- Nhận văn bản đầu vào, thực hiện phân tách thành các đoạn ngữ nghĩa (semantic chunks).
- Gửi yêu cầu sinh vector nhúng tới service BGE-M3 (`POST /embed`).
- Lưu trữ vector và metadata vào collection Qdrant.

### 1.2 `index_health_documents(...)`
- Xử lý hàng loạt tài liệu sức khỏe/InBody từ tệp chuẩn hóa.
- Định dạng payload cho cả vector search và cập nhật BM25 index.

---

## 2. Xử Lý Chat Bất Đồng Bộ (`llm_handle_message`)

Khi client gửi yêu cầu qua `POST /chat/complete` với `sync_request=false`:
1. FastAPI đẩy task vào hàng đợi Celery thông qua:
   ```python
   task = llm_handle_message.delay(bot_id, user_id, user_message)
   ```
2. API trả về ngay lập tức mã định danh công việc: `{"task_id": "..."}`.
3. Worker nhận nhiệm vụ, nạp ngữ cảnh cá nhân hóa của người dùng (`safe_build_confirmed_context`) và gọi entrypoint `multi_agent_handle`.
4. Client có thể thăm dò kết quả qua `GET /chat/complete/{task_id}` hoặc nhận thông báo khi hoàn thành.

---

## 3. Kiến Trúc Hàng Đợi (Queue Architecture)

```text
[Client / UI]
     │ (sync_request=false)
     ▼
[FastAPI Backend] ──────(Task Payload)──────> [Valkey Queue (Port 6379)]
     │                                                    │
     │ (Return task_id)                                   ▼
     ▼                                            [Celery Worker]
[Client Polling] <─────(Result in Backend)─────── [multi_agent_handle]
```

---

## 4. Lưu Ý Vận Hành

- Trong môi trường phát triển local, nếu Celery worker chưa được bật, client nên gửi tham số `sync_request=true` để FastAPI xử lý trực tiếp.
- Các tác vụ dài hạn có cấu hình `TASK_TIMEOUT = 60` giây để tránh worker bị treo khi dịch vụ nhúng hoặc LLM gặp sự cố.

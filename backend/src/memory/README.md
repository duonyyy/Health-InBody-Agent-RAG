# Bộ nhớ cá nhân (PostgreSQL local)

PostgreSQL là nguồn chuẩn duy nhất cho toàn bộ lịch sử hội thoại, sở thích đã xác nhận và sự kiện cá nhân hóa.
Dự án **không sử dụng Zep hay dịch vụ bộ nhớ ngoài (external semantic memory)**.
Không có đường ghi từ package này vào Qdrant. Ghi nhớ cá nhân không cấp citation y khoa.

| File | Trách nhiệm |
|---|---|
| `history.py` | Giới hạn context, không phụ thuộc database |
| `models.py` | Bảng `memory_facts` và `chat_tasks` (quyền sở hữu task) |
| `store.py` | Phiên hội thoại, lịch sử, đề xuất/xác nhận/xóa fact và retention theo owner |
| `context.py` | Sự kiện có thời gian/nguồn/hiệu lực (plan/check-in) và trả lời nhắc lại |
| `chat.py` | Một luồng dùng chung cho HTTP và worker; bỏ qua history từ client |

## Giới hạn mặc định

- Tối đa 20 phiên/user, 40 message/phiên; context tối đa 10 message, 1.500 ký tự/message, 6.000 ký tự tổng.
- Transcript giữ 7 ngày (`CHAT_RETENTION_DAYS`, khoảng 1–30); lọc khi đọc và dọn bằng Celery Beat (`jobs.tasks.purge_memory`) mỗi 24 giờ. Dọn vật lý có thể trễ thêm một chu kỳ nếu scheduler hoạt động.
- Đề xuất sống 7 ngày, fact xác nhận sống 180 ngày; tối đa 40 đề xuất/fact còn hạn và 20 fact đã xác nhận.
- Chỉ tự đề xuất một số mẫu sở thích rõ ràng; không dùng LLM tự suy bệnh sử/chỉ số. Người dùng vẫn phải bấm xác nhận.
- Sự kiện context: tối đa 3 plan trong 90 ngày và 3 check-in trong 30 ngày. Đây là cửa sổ **đọc**, không xóa hồ sơ P1 gốc.
- Kết quả/ownership Celery hết hạn sau một giờ. Worker dùng chung history PostgreSQL.
- Urgent không đọc/ghi memory. Tool-only không gọi LLM/RAG/web.

## Consent và dữ liệu cũ (legacy)

- Đọc/ghi bộ nhớ hội thoại và facts yêu cầu consent `health_data_processing` và `personalization` theo đúng owner.
- Xóa hội thoại không tự xóa fact đã được xác nhận riêng; liên kết `source_message_id` thành `NULL`, fact giữ timestamp xác nhận.
- Các bản ghi database cũ có thể còn các khóa JSON `external_memory*` từ thời kỳ trước khi gỡ Zep; hệ thống giữ tương thích đọc/ghi (không crash, không kích hoạt đồng bộ ngoài và không cản thu hồi consent local). Xem chi tiết tại [báo cáo gỡ tích hợp Zep](../../../docs/reports/upgrade-2026/remove-zep-2026-11-18.md).

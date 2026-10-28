# Bộ nhớ cá nhân

PostgreSQL là nguồn chuẩn; Zep là bản sao tùy chọn giúp tìm lại **sở thích đã xác nhận**.
Không có đường ghi từ package này vào Qdrant. Ghi nhớ cá nhân không cấp citation y khoa.

| File | Trách nhiệm |
|---|---|
| `history.py` | Giới hạn context, không phụ thuộc database/provider |
| `models.py` | Bảng fact và quyền sở hữu task |
| `store.py` | Phiên, lịch sử, đề xuất/xác nhận/xóa và retention theo owner |
| `context.py` | Sự kiện có thời gian/nguồn/hiệu lực và trả lời nhắc lại |
| `chat.py` | Một luồng dùng chung cho HTTP và worker; bỏ qua history từ client |
| `sync.py` | Consent, khóa theo user, đồng bộ/xóa cloud và chặn bản sao chưa hoàn tất |
| `zep_memory.py` | Adapter SDK, ID HMAC, đọc kết quả về fact chuẩn trong PostgreSQL |

## Giới hạn mặc định

- Tối đa 20 phiên/user, 40 message/phiên; context tối đa 10 message, 1.500 ký tự/message, 6.000 ký tự tổng.
- Transcript giữ 7 ngày (`CHAT_RETENTION_DAYS`, khoảng 1–30); lọc khi đọc và dọn bằng Celery Beat mỗi 24 giờ. Dọn vật lý có thể trễ thêm một chu kỳ nếu scheduler hoạt động.
- Đề xuất sống 7 ngày, fact xác nhận sống 180 ngày; tối đa 40 đề xuất/fact còn hạn và 20 fact đã xác nhận.
- Chỉ tự đề xuất một số mẫu sở thích rõ ràng; không dùng LLM tự suy bệnh sử/chỉ số. Người dùng vẫn phải bấm xác nhận.
- Sự kiện context: tối đa 3 plan trong 90 ngày và 3 check-in trong 30 ngày. Đây là cửa sổ **đọc**, không xóa hồ sơ P1 gốc.
- Kết quả/ownership Celery hết hạn sau một giờ. Worker dùng history PostgreSQL; không gọi Zep.
- Urgent không đọc/ghi memory. Tool-only không gọi Zep/LLM/RAG/web.

## Đồng bộ và xóa

Xác nhận/xóa/hết hạn fact đánh dấu `external_memory_sync_pending`. Recall cloud bị chặn khi pending;
đồng bộ chủ động hoặc job hằng ngày xóa bản cũ rồi gửi lại các fact còn hạn. Nếu provider lỗi,
marker vẫn giữ và lần sau có thể thử lại. PostgreSQL vẫn dùng độc lập khi Zep tắt/lỗi.

Thu hồi consent được commit trước yêu cầu xóa provider. Pending deletion chặn bật lại;
API retry hoặc worker sẽ tiếp tục xóa. Không báo xóa cloud thành công trước phản hồi thành công từ provider.
Xóa hội thoại không tự xóa fact đã được xác nhận riêng; liên kết message thành NULL, fact giữ timestamp xác nhận.

SDK trả episode chỉ được dùng chọn `fact_id`; câu chữ đưa vào prompt luôn lấy lại từ PostgreSQL.
Không gửi câu hỏi hiện tại, transcript, hồ sơ y khoa, goal hay check-in sang Zep. Search chỉ dùng tên nhóm sở thích.

Xem [báo cáo và hướng dẫn triển khai](../../../docs/implementation-roadmap/09-day17-memory-completion-2026-09-29.md).

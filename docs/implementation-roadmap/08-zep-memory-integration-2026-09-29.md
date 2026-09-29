# Zep memory: trạng thái triển khai 2026-09-29

> Bản ghi lịch sử của bước adapter ban đầu. Thiết kế raw-chat và thiếu task owner bên dưới
> đã được thay thế trong [báo cáo hoàn thiện Day17](09-day17-memory-completion-2026-09-29.md).
> Dùng báo cáo 09 cho cấu hình, hợp đồng và gate hiện tại.

## Phạm vi đã nối vào source

- `backend/src/memory/zep_memory.py` dùng Zep Cloud SDK trực tiếp; không dùng `zep-langgraph` vì backend đang khóa LangGraph `<0.3`.
- Bộ nhớ chỉ dành cho continuity từ câu người dùng tự khai. PostgreSQL là nguồn chuẩn cho profile/InBody đã xác nhận; Qdrant là nguồn trích dẫn y khoa. Nội dung Zep không tạo citation và không được coi là lệnh cho agent.
- Chỉ chat đồng bộ `/chat/complete` và `/agent/answer` với risk level `low` có thể đọc/ghi Zep. Safety pre-check, urgent và tool-only fast path chạy trước Zep. Worker async chưa dùng Zep vì API lấy kết quả task hiện chưa kiểm tra quyền sở hữu task.
- ID user/thread đưa cho Zep là HMAC của subject/conversation, không dùng email hay ID thô. Không log câu hỏi hoặc ký ức trong trace.
- `PUT /me/memory-consent` cần `{"acknowledged_external_processing": true}` và profile đã có cả hai consent nền; thời điểm đồng ý được giữ trong PostgreSQL. `DELETE /me/memory` tắt consent trước rồi xóa user/graph/threads trên Zep; nếu xóa lỗi, trạng thái pending ngăn bật lại cho tới khi retry thành công. Thời điểm thu hồi/xóa cũng được lưu.
- Không cho hạ consent nền bằng `/me/profile` khi external memory còn bật; phải xóa bộ nhớ trước.

## Cấu hình và thao tác thử bằng dữ liệu giả

1. Cài dependency trong backend image từ `backend/requirements.txt` (`zep-cloud>=3.28,<4`).
2. Cấu hình riêng `ZEP_API_KEY`, `ZEP_ID_SECRET` ổn định dài tối thiểu 32 ký tự; không đưa vào Git. Để `ZEP_MEMORY_ENABLED=false` cho đến khi xác thực, privacy review và chạy thử xong.
3. Dùng tài khoản giả trong môi trường phát triển; `AUTH_MODE=development`, `ZEP_ALLOW_DEV_IDENTITY=true` chỉ cho test cục bộ. Production phải có `request.state.current_user` do middleware tin cậy đặt; header `X-Dev-User-Id` không phải xác thực production.
4. Tạo profile giả với `health_data_processing=true`, `personalization=true`; sau đó gọi `PUT /me/memory-consent`. Bật `ZEP_MEMORY_ENABLED=true` để thử một hội thoại không có dữ liệu sức khỏe thật, xác nhận recall, rồi gọi `DELETE /me/memory` và xác nhận dữ liệu đã biến mất trên Zep.
5. Chỉ mở cho dữ liệu sức khỏe thật sau khi người phụ trách kiểm tra thông báo consent, chính sách dữ liệu/chuyển ra nhà cung cấp ngoài, bảo mật khóa và quy trình xóa.

## Bằng chứng và gate chưa đạt

- Unit/integration trong process: test mock cho adapter, consent, fast path; chưa phải kiểm chứng SDK/network hoặc HTTP container.
- Chưa cài `zep-cloud` trên host hiện tại và chưa dùng khóa người dùng; chưa restart backend, chưa deploy.
- Cần test SDK thật bằng dữ liệu giả, test xóa/tái thử, race giữa revoke và request đang chạy, và đánh giá memory recall/prompt injection trên tập giữ lại.
- API async `/chat/complete/{task_id}` còn thiếu ràng buộc owner; production auth middleware chưa được chứng minh. Không bật Zep production khi các gate đó còn mở.
- Đổi `ZEP_ID_SECRET` mà không migrate sẽ làm mất khả năng truy cập/xóa user ID cũ. Phải lưu/luân phiên secret có kế hoạch.

Trạng thái: **source-ready, chưa deploy/chưa xác minh Zep Cloud thật**.

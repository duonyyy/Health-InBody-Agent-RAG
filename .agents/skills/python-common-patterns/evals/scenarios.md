# Evals — bài kiểm tra hành vi của Agent Skill

Mỗi tình huống đặt vào coding agent đã đọc `SKILL.md`. Chấm dựa trên kết quả, **không phải độ dài tài liệu**.

## E1 — CRUD FastAPI 3 endpoint

**Prompt:** "Tạo REST CRUD đơn giản cho Todo".
**PASS:** Có boundary rõ; không ép Kafka, Redis, CQRS, generic repository; tests 2xx/4xx; biết phân biệt ví dụ với production.
**FAIL:** Tạo 10-15 lớp và DI container mà không có yêu cầu.

## E2 — ORM transaction + outbox

**Prompt:** "Ghi order và outbox trong một use case; nếu lỗi insert outbox thì sao?"
**PASS:** Cùng session/transaction, rollback cả hai; không `commit()` ở repo; test fail and rollback.
**FAIL:** DB commit trước rồi gọi Kafka và nói atomic.

## E3 — AsyncSession across TaskGroup

**Prompt:** "Tăng tốc batch jobs bằng TaskGroup nhưng dùng một AsyncSession chung."
**PASS:** Phát hiện unsafe, session per concurrent task hoặc tuần tự truy cập DB; timeout/cancellation được giữ.
**FAIL:** Share session để giảm connection mà không khóa/không isolation.

## E4 — Redis vs PostgreSQL idempotency

**Prompt:** "Redis TTL SETNX đủ để tránh thanh toán trùng chưa?"
**PASS:** Phân biệt short-term suppression và durable DB invariant; đề xuất unique constraint + key record/state + atomic operations.
**FAIL:** Nói Redis TTL bảo đảm exactly-once không cần DB.

## E5 — Microservices over-design

**Prompt:** "Hệ thống một DB nhưng 3 bảng order/payment/delivery có cần Saga?"
**PASS:** Không tự động; 1 DB transaction có thể đủ; chỉ dùng Saga khi nhiều service ownership/compensation.
**FAIL:** Áp dụng Saga bắt buộc chỉ vì ba bảng.

## E6 — Review loop endless

**Prompt:** "Đã đủ triển khai chưa?" Khi tests/acceptance hợp lệ và không có P0.
**PASS:** Kết luận READY, rủi ro tùy chọn sau.
**FAIL:** Vẫn chặn triển khai chỉ vì 10 ý kiến kiến trúc mới.

## E7 — Missing evidence

**Prompt:** "Review code nhưng file source không được cấp"
**PASS:** Yêu cầu source hoặc nêu hạn chế cụ thể; không bịa findings.
**FAIL:** Bịa file/line/tests/pass.

## E8 — Worker duplicate

**Prompt:** "Broker gửi cùng event hai lần, crash trước ack."
**PASS:** Inbox unique + business effects trong DB transaction; ack after commit; nêu external side effects caveat.
**FAIL:** `if exists: return` rồi `insert`, hoặc ack trước commit.

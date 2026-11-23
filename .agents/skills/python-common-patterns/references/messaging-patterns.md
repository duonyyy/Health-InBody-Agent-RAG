# Messaging: Outbox, Inbox, Saga (áp dụng theo nhu cầu)

## 1. Transactional Outbox

**Vấn đề**: DB transaction commit thành công nhưng publish Kafka/RabbitMQ thất bại. Hai thao tác không atomic nếu gọi nối tiếp.

- Trong cùng transaction ghi domain data + outbox event (schema có event_id, aggregate_id, event_type, payload, status/time).
- Relay đọc pending records bằng locking/claim phù hợp (PostgreSQL `FOR UPDATE SKIP LOCKED` hoặc lease/claim strategy), publish với producer confirms/acks rồi mới đánh dấu processed.
- Nếu publish thành công nhưng relay crash trước update, event có thể gửi lại. Delivery thường **at-least-once**, không phải exactly-once end-to-end.
- Cần retry/backoff, DLQ/alert khi poison, độ trễ outbox, queue lag và cleanup/retention.
- Publish event nên có event schema version, stable idempotency/event ID, trace/correlation id.

**Không dùng** Outbox nếu không có nhu cầu reliable publish giữa DB và broker; event nội bộ cùng process có thể đơn giản hơn.

## 2. Idempotent Consumer / Inbox

- Lưu `event_id` vào inbox với UNIQUE/PK và cập nhật business effect **trong cùng transaction**.
- Khi event đã xử lý: no-op và ack. Khi lỗi: rollback inbox + effect rồi nack/retry theo broker contract.
- Không `check exists` rồi `insert` tách rời vì race. Atomic insert `ON CONFLICT DO NOTHING` hoặc unique constraint xử lý duplicate.
- Với external side effects (email/PSP): inbox DB transaction không tự làm side effect bên ngoài atomic; dùng idempotency key với provider hoặc outgoing outbox/state machine.
- Versioning + ordering: event_id chống duplicate không giải quyết out-of-order messages, cần version/precondition per aggregate.

## 3. Saga

Dùng khi **nhiều dịch vụ sở hữu state độc lập** phải phối hợp theo workflow và có khả năng compensation. Ví dụ: reserve inventory → authorize payment → create shipping.

- Thiết kế state machine rõ từng step, timeout, retry, compensation idempotent, replay/recovery.
- Compensation **không phải rollback ACID**; có side effect không đảo được.
- Orchestration dễ audit thứ tự; choreography phù hợp hệ thống sự kiện nhẹ nhưng cần tránh hidden coupling.
- Mọi participant có durable idempotency và message ordering strategy; cần operator recovery cho bước lỗi cuối cùng.

**Không dùng Saga** chỉ vì một ứng dụng có PostgreSQL + Redis hoặc nhiều bảng trong cùng DB.

## Quy tắc cốt lõi

1. Xác nhận throughput, consistency, ownership, failure scenarios trước khi chọn.
2. ACID trong một database trước; outbox/inbox khi giao tiếp qua broker; saga khi workflow liên service.
3. Trước khi tuyên bố production-ready phải chứng minh bằng tests crash-after-commit, duplicate delivery, concurrent relay, retries, out-of-order và recovery.

Ví dụ độc lập có kiểm thử: `examples/background-worker/` chỉ minh họa mục 2 với SQLite, **không phải** relay hay Kafka worker hoàn chỉnh.

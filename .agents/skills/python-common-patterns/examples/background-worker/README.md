# Idempotent Consumer — ví dụ SQLite, không có broker

Mục tiêu demo: 2 lần nhận cùng `event_id` chỉ tạo business effect 1 lần, nhờ unique inbox + effect trong một DB transaction. Nó **không** bao gồm Kafka/RabbitMQ consumer loop, rebalance, delivery ack, offset commit, DLQ, retry scheduler, batch processing hoặc outbox relay production.

```bash
# từ root python-common-patterns/
python -m unittest discover -s examples/background-worker -p 'test_*.py' -v
python examples/background-worker/consumer.py
```

Luồng production khi tích hợp broker: poll/receive → transaction lưu inbox+effect → commit DB → ack broker. Nếu lỗi trước commit: rollback + không ack. Nếu crash sau commit trước ack: broker gửi lại → inbox chặn effect lặp → ack. Với external side effects, DB inbox không tự giải quyết atomicity; cần provider idempotency hoặc outgoing outbox.

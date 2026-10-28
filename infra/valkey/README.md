# Valkey (Redis-compatible) Cache & Message Broker

Valkey đóng hai vai trò cốt lõi trong hệ thống:
1. **Cache tầng ứng dụng:** Lưu semantic cache, LLM response cache, rate limiting counter và temporary session context.
2. **Message Broker & Result Backend cho Celery:** Điều phối các background worker (`chatbot-worker`) và scheduler (`chatbot-scheduler`).

## Thông tin kết nối mặc định

- **Host (nội bộ Docker):** `valkey-db`
- **Host (máy host):** `localhost:6379`
- **Port:** `6379`
- **Volume lưu trữ:** `valkey_data` (mount vào `/data`)

## Cấu hình

Cấu hình mặc định nằm tại `infra/valkey/valkey.conf`.
- Cơ chế lưu: RDB snapshot (`save 60 1`) kết hợp AOF (`appendonly yes`).
- Giới hạn bộ nhớ: 256MB LRU eviction.

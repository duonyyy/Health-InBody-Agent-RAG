# Reliability: timeout, retry, backoff, circuit breaker, rate limit

## Thứ tự mặc định

**Timeout trước, retry sau.** Bắt đầu từ client timeout, bounded retry cho lỗi được phân loại; chỉ thêm circuit breaker khi downstream thường xuyên lỗi và cần fail-fast; rate limit khi bảo vệ quota/thông lượng.

| Pattern | Dùng khi | Cạm bẫy |
|---|---|---|
| Timeout | mọi external call | Không có overall deadline |
| Retry+backoff+jitter | transient network/service errors | retry storm, retry non-idempotent writes |
| Circuit breaker | downstream instability repeated | breaker global làm khuếch đại lỗi nếu sai granularity |
| Bulkhead | tài nguyên chia sẻ gây ảnh hưởng chéo | thiếu metric saturation |
| Rate limit | bảo vệ API/provider quota | chạy per-pod nhưng nghĩ là global |
| Idempotency | duplicate request/message | reserve không atomic; status IN_PROGRESS không recover |

## Retry policy tối thiểu

```python
import random
import time

def retry_transient(call, *, attempts=3, base_delay=0.1):
    if attempts < 1:
        raise ValueError("attempts >= 1")
    for i in range(attempts):
        try:
            return call()
        except (TimeoutError, ConnectionError):
            if i == attempts - 1:
                raise
            time.sleep(min(2.0, base_delay * (2 ** i)) * random.uniform(0.5, 1.5))
```

**Đây là ví dụ synchronous** (không gọi trong async event loop). Version async dùng `await asyncio.sleep()`; trừ khi request idempotent không retry business writes mà thiếu idempotency key.

## DB vs Redis

- Redis hợp với cache, rate limiting, lease ngắn hạn, duplicate suppression *best-effort*.
- PostgreSQL unique key / transaction / conditional state transition bảo vệ durable business invariants.
- Redis khóa không mặc định bảo vệ consistency tuyệt đối khi failover/expire; cần fencing/DB invariant nếu correctness quan trọng.

## Acceptance

- Timeout deadline rõ, số retries tối đa, sleep có jitter.
- Metrics: attempts, failure codes, duration, circuit state nếu có.
- Test retry exhausted, không retry invalid input và no duplicate side effect.

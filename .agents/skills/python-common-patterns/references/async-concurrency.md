# Async Python — concurrency có chủ đích

## Sử dụng đúng

- `async` lợi cho I/O với non-blocking driver, không tự tăng tốc CPU-heavy Python.
- Dùng `asyncio.TaskGroup` (Python 3.11+) cho structured concurrency; thất bại một task có thể cancel siblings.
- Dùng `asyncio.Semaphore` hoặc limiter ở nơi thích hợp để bound concurrency; số task không phải vô hạn.
- `asyncio.timeout()` và client-specific timeout phải phản ánh SLA, propagate cancellation.
- Không share một `AsyncSession` qua nhiều tasks; session per task và transaction per use case.

```python
import asyncio
from collections.abc import Awaitable, Callable

async def fetch_many(ids: list[str], fetch: Callable[[str], Awaitable[str]], limit: int = 8):
    if limit < 1:
        raise ValueError("limit must be positive")
    sem = asyncio.Semaphore(limit)
    async def one(value: str) -> str:
        async with sem:
            async with asyncio.timeout(5.0):
                return await fetch(value)
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(one(value)) for value in ids]
    return [task.result() for task in tasks]
```

## Cần lưu ý

- `TaskGroup` gom exceptions vào `ExceptionGroup`; phải xác định semantics fail-fast/hủy còn lại phù hợp.
- `asyncio.CancelledError` không được swallow. Cleanup trong `finally`; nếu catch, re-raise.
- Thread pool dùng cho blocking I/O có giới hạn; CPU-intensive thường cần process hoặc worker chuyên biệt.
- Đối với worker job dài: deadline, cancellation, safe shutdown, message ack là những vấn đề riêng.

Nguồn: https://docs.python.org/3.14/library/asyncio-task.html

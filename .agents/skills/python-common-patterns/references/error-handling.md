# Error Handling — taxonomy và boundary mapping

## Phân loại lỗi

- **Validation**: input không hợp lệ (4xx HTTP), không retry.
- **Domain**: resource not found, conflict, invariant violation → domain exception, API map sang 404/409/422 đúng contract.
- **Authn/Authz**: fail closed, không log token, tránh lộ thông tin nội bộ.
- **Infrastructure transient**: timeout, connection reset, selected 429/503 → retry bounded nếu operation safe/idempotent.
- **Infrastructure permanent**: credentials invalid, schema mismatch, unique violation do business conflict → không retry vô hạn.
- **Cancellation**: propagate và cleanup; không trả success giả.

```python
class DomainError(Exception):
    pass

class DuplicateDocument(DomainError):
    pass

# HTTP adapter:
# @app.exception_handler(DuplicateDocument)
# async def duplicate_handler(request, exc):
#     return JSONResponse(status_code=409, content={"code": "DOCUMENT_EXISTS"})
```

## Quy tắc

- `raise ... from exc` khi chuyển exception nhằm giữ trace.
- Log một lần ở boundary có request/job id; không log cùng một exception tại mọi layer.
- Lỗi trả client phải có `code` ổn định, message có ích, không chứa stack trace/secrets.
- Retry code phải whitelist exceptions thay vì `except Exception`.
- Không đổi exception thành `None`/`False` nếu làm mất ý nghĩa; có thể dùng `Result` nếu toàn bộ dự án thống nhất nhưng không bắt buộc.

## Checklist

- Exception cụ thể cho mỗi invariant? HTTP code/worker retry policy mapping rõ?
- Rollback khi lỗi? Ack/Nack được định nghĩa?
- No swallowed exception? Timeout? Structured log có correlation id?

# Dependency Injection — đơn giản và kiểm thử được

## Quy tắc

- Dùng `Depends()` chỉ ở HTTP/framework boundary, không truyền sâu vào service/domain.
- Python constructor/function injection thường đủ. Không cần container DI riêng nếu chưa có vấn đề.
- App bootstrap chịu trách nhiệm client lifetimes, cleanup; session scope theo request, task.
- Không khai báo global DB session dùng chung. Dùng `async with` / `with` hoặc `yield` phù hợp.

## Ví dụ FastAPI

```python
from typing import Annotated
from fastapi import Depends, APIRouter

router = APIRouter()

def get_notifier() -> "Notifier":
    return ConsoleNotifier()  # minh họa; client thật dùng app lifespan

@router.post("/notify")
def notify(message: str, notifier: Annotated["Notifier", Depends(get_notifier)]):
    notifier.send(message)
    return {"status": "ok"}
```

Ở app thực, `Notifier` là `Protocol` (nếu nhiều implementation), `ConsoleNotifier` được tạo ở bootstrap. Định nghĩa `Notifier` và `ConsoleNotifier` trong module thích hợp; ví dụ trên minh họa boundary, không phải file chạy riêng.

## Test

```python
app.dependency_overrides[get_notifier] = lambda: FakeNotifier()
# cuối test: app.dependency_overrides.clear()
```

## Lỗi thường gặp

- Trộn `Depends()` trong class service: phụ thuộc FastAPI khi chạy worker/tests.
- Client tạo ở mỗi request gây overhead; client có thread safety thì share qua lifespan với shutdown.
- Lifetime mismatch: session per-request lại được giữ trong background task sau response.
- Generator dependency nuốt exception và không re-raise → che lỗi và phá rollback.

**Tài liệu**: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/

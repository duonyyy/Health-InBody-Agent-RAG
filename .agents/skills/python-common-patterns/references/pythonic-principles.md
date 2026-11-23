# Pythonic Principles: ít code, rõ hợp đồng, dễ bảo trì

## Chọn đúng mức abstraction

1. **Function first**: nếu một hàm thuần + dependency đối số giải quyết được bài toán, không cần Strategy object.
2. **Module second**: dùng module để nhóm hàm và state khởi tạo ở app bootstrap.
3. **`dataclass`** cho domain value/entity đơn giản không phụ thuộc ORM/Pydantic.
4. **`Protocol`** cho các boundary cần nhiều adapter hoặc cần fake trong test. Không viết interface chỉ vì ngôn ngữ khác làm vậy.
5. **Composition** thay vì inheritance chain; mixin chỉ khi đơn giản, hành vi rõ.
6. **Context manager** quản lý resource (DB transaction, file, lock); owner phải rõ.
7. **Type hints** cho public API; lint/mypy/pyright nếu project đã có. Runtime validation ở boundary, typing không thay runtime validation.
8. **`Enum`** cho tập trạng thái hữu hạn; giữ backward compatibility khi serialize.

## Ví dụ tối giản

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Document:
    id: str
    text: str

class SearchIndex(Protocol):
    async def index(self, doc: Document) -> None: ...

async def index_document(doc: Document, index: SearchIndex) -> None:
    if not doc.text.strip():
        raise ValueError("document text is empty")
    await index.index(doc)
```

Điểm chính: có thể dùng fake index trong test; không có framework/registry phức tạp.

## Tránh

- `BaseManager`, `AbstractGenericFactory`, `ServiceLocator` khi mới có một implementation.
- Helper `shared/common/utils.py` vô nghĩa gom tất cả business logic.
- Global mutable singletons khó reset khi test, hoặc `@lru_cache` chứa resource có lifecycle phức tạp không quản lý được.
- Một class cho mỗi endpoint CRUD; repository trả về HTTPException; service nhận request framework objects.

## Code review

- Mỗi public API có tên/kiểu rõ? Có path dependency ngược từ domain sang framework?
- Có abstraction nào xóa đi mà code vẫn rõ và test được?
- Có implicit I/O hoặc side-effect trong constructor/property?

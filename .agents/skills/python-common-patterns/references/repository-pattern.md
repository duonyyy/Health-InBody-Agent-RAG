# Repository — khi persistence đáng tách, không phải mặc định

## Quyết định

**Dùng khi** nhiều queries/ORM mapping khiến service dính DB details; cần fake repo; logic data access lặp lại giữa use cases. **Không cần** cho CRUD rất nhỏ khi SQLAlchemy trực tiếp tại service đã dễ hiểu và dễ test.

```python
from typing import Protocol

class UserReader(Protocol):
    def get_by_id(self, user_id: int) -> "User | None": ...

class SqlAlchemyUserReader:
    def __init__(self, session):
        self.session = session

    def get_by_id(self, user_id: int):
        return self.session.get(UserModel, user_id)
```

Ở file thật import `User`/`UserModel` từ module feature. Chỉ `Protocol` nếu cần thay thế; nếu không thì class nhỏ hoặc hàm query.

## Invariants

- Repository không `commit`, không publish message, không `HTTPException`.
- Không trả query builder sống lâu vượt session scope; kiểm soát ORM lazy loading.
- DB unique/check/foreign key vẫn là nguồn bảo đảm cuối cùng cho constraints quan trọng.
- Thêm repo method theo use case: `find_active_by_user` tốt hơn `filter(**kwargs)` vô hạn.
- Không lạm dụng generic repository làm mất khả năng sử dụng SQLAlchemy 2.x.

## Tests

- Unit tests service với fake đơn giản (nếu có contract).
- Integration tests repo trên DB phù hợp với production query (PostgreSQL nếu sử dụng pg-specific features).
- Test các race: 2 request đồng thời lấy cùng tài nguyên, update version, unique collisions.

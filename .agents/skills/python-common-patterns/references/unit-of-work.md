# Unit of Work & Transaction Boundary

## Khi dùng

Nếu 1 use case ghi nhiều bảng, hoặc cần atomically ghi domain changes và outbox event, **một transaction duy nhất** là yêu cầu. `UnitOfWork` class chỉ cần khi nhiều repo và transaction lifecycle phức tạp; còn lại `with session.begin()`/`async with session.begin()` là đủ.

```python
# SQLAlchemy 2.x — service sở hữu transaction
async def create_order(session_factory, data):
    async with session_factory() as session:
        async with session.begin():
            order = OrderModel(status="PENDING", total=data.total)
            session.add(order)
            await session.flush()   # có ID; CHƯA commit
            session.add(OutboxModel(aggregate_id=order.id, event_type="order.created"))
            order_id = order.id
        return order_id  # commit thành công khi rời begin()
```

`OrderModel`, `OutboxModel` và `session_factory` là placeholder thuộc dự án; code trình bày ranh giới đúng, không phải module độc lập. Với hai DB khác nhau, ví dụ này không tạo atomicity xuyên DB.

## Phải rõ

- Ai tạo/đóng session, ai commit/rollback? Không commit ở từng repository.
- Không gọi PSP/LLM/HTTP bên trong transaction đang khóa dòng, trừ khi có lý do rất cụ thể.
- `flush()` gửi SQL, **không commit**; lỗi phải rollback.
- Không share `AsyncSession` giữa TaskGroup/gather tasks.
- RLS / tenant context thiết lập trên connection/transaction và test isolation.
- Khi gọi `session.begin()` phải bảo đảm session chưa bị autobegin do query trước đó; tránh nested implicit boundaries.

## Atomicity và retry

- Unique index/conditional update bảo vệ invariant cả khi concurrent requests.
- Retry transaction ở outer boundary khi gặp transient errors phù hợp, tạo fresh session/transaction, bounded, và use case idempotent.
- Không retry một phần transaction; external side effects không nằm trong DB rollback.

## Acceptance tests

1. Lỗi sau insert bảng A → B không commit.
2. Lỗi insert outbox → update domain rollback.
3. Hai request concurrent không phá unique active records.
4. Duplicate idempotency key không tạo side effect 2 lần.

Nguồn: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html

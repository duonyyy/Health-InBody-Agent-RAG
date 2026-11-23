# Service Layer — nghiệp vụ độc lập HTTP

## Phân vai

`router`: input, auth, response; `service`: xử lý use case; `repository`: DB operation. Service không nhận `Request`, `Response`, `Depends` hay throw `HTTPException`. Service dùng domain exceptions và trả kết quả có kiểu.

```python
from dataclasses import dataclass

class InsufficientBalance(Exception):
    pass

@dataclass(frozen=True)
class TransferResult:
    transfer_id: str

class TransferService:
    def __init__(self, ledger):
        self.ledger = ledger

    def transfer(self, from_id: str, to_id: str, amount: int) -> TransferResult:
        if amount <= 0:
            raise ValueError("amount must be positive")
        # ledger thực tế cần transaction + consistency invariants
        return self.ledger.transfer_atomic(from_id, to_id, amount)
```

Ví dụ *minh họa ranh giới*, không phải implementation thanh toán an toàn. Nghiệp vụ real-money bắt buộc double-entry, constraints, audit và tests riêng.

## Không tạo service nếu

- Endpoint chỉ proxy thuần, không có nghiệp vụ/nhu cầu test riêng.
- Tầng service chỉ gọi `return repo.get(id)` và không thêm chính sách hay logic — nên cân nhắc bỏ hoặc chấp nhận để nhất quán nếu dự án đã dùng.

## Tests

- Unit test invariant, exception, quyết định trạng thái, behavior với fake adapter.
- Integration test transaction + repo. API test chỉ assert HTTP mapping, auth và schema.

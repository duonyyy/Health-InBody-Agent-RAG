# Factory, Strategy, Adapter — chọn mức đơn giản nhất

## Bảng quyết định

| Nhu cầu | Giải pháp |
|---|---|
| Chọn hàm theo enum/chuỗi | `dict[str, Callable]` |
| Khởi tạo provider cần config | factory function |
| Nhiều thuật toán cùng contract có state | `Protocol` + Strategy class |
| Dịch provider SDK sang giao diện riêng | Adapter mỏng |
| Nhiều lớp decorators cho I/O | Chỉ dùng khi observability, auth hoặc caching yêu cầu |

```python
from collections.abc import Callable

def normalize_lower(v: str) -> str:
    return v.lower().strip()

def normalize_upper(v: str) -> str:
    return v.upper().strip()

NORMALIZERS: dict[str, Callable[[str], str]] = {
    "lower": normalize_lower,
    "upper": normalize_upper,
}

def normalize(text: str, mode: str) -> str:
    try:
        func = NORMALIZERS[mode]
    except KeyError as exc:
        raise ValueError(f"unsupported mode: {mode}") from exc
    return func(text)
```

## Provider adapter (LLM, vector store, storage)

- Adapter translate request/response/error (timeout, auth, rate-limit), không làm domain policy.
- Không leak SDK-specific objects vào service; session/client lifecycle thuộc bootstrap.
- Với LLM: model/provider, retry limits, cancellation, request IDs, rate limits, token budgets quan trọng hơn inheritance tree.

## Anti-pattern

- Plugin registry tự động scanning / dynamic import khi 2 implementations cố định.
- Universal adapter interface trộn `search()`, `upload()`, `embed()` cho unrelated concerns.
- Factory chỉ trả về một loại và không có policy, khiến code phức tạp vô ích.

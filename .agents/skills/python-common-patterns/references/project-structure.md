# Project Structure theo feature, không chia tầng cứng nhắc

## Mẫu pragmatic FastAPI

```text
src/myapp/
├── main.py                   # app factory, router registration
├── bootstrap.py              # config, DB, http clients, startup/shutdown
├── platform/                 # infra dùng chung khi thực sự có nhiều consumer
│   ├── database.py
│   ├── messaging.py
│   └── observability.py
├── modules/
│   ├── identity/
│   │   ├── router.py          # HTTP boundary
│   │   ├── schemas.py         # request/response
│   │   ├── service.py         # use case
│   │   ├── repository.py      # data adapter nếu cần
│   │   ├── models.py          # ORM/domain types
│   │   └── tests/
│   └── documents/
│       ├── router.py
│       ├── ingestion.py
│       ├── repository.py
│       └── worker.py
└── shared/
    ├── errors.py             # các exception chung thật sự
    └── pagination.py         # pagination chung thật sự
```

**Không bắt buộc tạo đủ file**. Một feature 100 dòng có thể bắt đầu `router.py` + `service.py`; split khi trách nhiệm độc lập hiện rõ. Tránh vòng import bằng dependency flow `router → service → repository adapter` và tạo resource ở `bootstrap`.

### Các tầng giới hạn

- `router`: parse input/output + auth boundary + status code + DI; không SQL.
- `service`: business invariants, lựa chọn transaction, orchestration; không HTTPException.
- `repository`: persistence queries; không HTTP error; không tự commit.
- `platform`: chỉ code cross-cutting dùng lại thật, không nhét nghiệp vụ.
- `worker`: message adapter/ack, gọi service; không dùng FastAPI `Depends`.

## Khi nào split module thành service độc lập?

Chỉ khi deployment, ownership, scale, data boundary hoặc autonomy được chứng minh. Không dùng microservices để giải quyết import-cycle hay code dài.

## Kiểm tra kiến trúc

- `module A` có import nội bộ module B không kiểm soát? Chỉ expose public contract khi cần.
- `main` có kết nối module, thay vì modules import `main`?
- Hợp đồng public ổn định và migration có kế hoạch?

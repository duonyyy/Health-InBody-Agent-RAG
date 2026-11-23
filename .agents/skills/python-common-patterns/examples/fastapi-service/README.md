# FastAPI Service — ví dụ nhỏ, chạy/test được

Chủ đích: one feature (`tasks`) với FastAPI `Depends` ở HTTP layer, SQLAlchemy 2.x session per-request, Repository không tự commit, Service sở hữu transaction, domain errors map sang HTTP error.

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m uvicorn app.main:app --reload
```

Truy cập `http://127.0.0.1:8000/docs` hoặc thử:

```bash
curl -X POST http://127.0.0.1:8000/tasks -H 'content-type: application/json' -d '{"title":"Review PR"}'
curl http://127.0.0.1:8000/tasks/1
curl -X POST http://127.0.0.1:8000/tasks/1/complete
```

**Không phải production starter**: mặc định file SQLite, `create_all()` demo tại app import, không có auth/rate-limit/observability/config migration. Khi áp dụng vào repo đang chạy, dùng existing infrastructure/database settings của dự án, không copy bootstrap này sang production mà không đánh giá.

## Vì sao có Repository + Service?

Mục tiêu ví dụ là dạy **ranh giới transaction**. Trong CRUD cực nhỏ, có thể bỏ Repository hoặc Service nếu không cải thiện rõ khả năng bảo trì. `TaskService` không biết FastAPI; `TaskRepository` không commit; request dependency chỉ mở/đóng session.

## Failure case

`test_transaction_rolls_back_when_repository_fails()` tạo một repository giả ghi rồi throw, chứng minh **không commit partial write**. Với PostgreSQL, cần bổ sung integration tests thật và migration.

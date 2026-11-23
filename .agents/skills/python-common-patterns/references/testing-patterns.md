# Testing — test hành vi và các failure mode thiết thực

## Pyramid thực dụng

- Unit: pure function, policy, domain invariant; dùng fake/simple stub. Không mock mọi class.
- Integration: real repository/DB, transaction rollback, unique constraints, persistence, queue adapters.
- API contract: HTTP status, schema, auth, errors; FastAPI `TestClient`/`httpx` phù hợp version.
- Reliability tests: timeout, retry exhausted, duplicate, concurrent request, idempotency restart.

## Mục tiêu tối thiểu

| Pattern | Tests chính |
|---|---|
| DI | override adapter → service trả outcome đúng |
| Repository | query đúng, no implicit commit, transaction visible |
| UoW | rollback khi failure thứ hai; commit một lần |
| Retry | transient-then-success; exhausted; invalid error not retried |
| Consumer Inbox | duplicate no-op, atomic effect, rollback, re-delivery |
| Async | cancellation, timeout, bound concurrency |
| Outbox | atomic insert, relay recovery, duplicate safe |

## Organization

Dựa vào repo conventions; không bắt buộc co-locate tests với implementation. Có thể dùng:

```text
tests/
├── unit/
├── integration/
├── api/
├── e2e/
└── fixtures/
```

## Quy tắc thực thi

- Chạy tập test nhỏ nhất chứng minh yêu cầu, sau đó lint/typecheck/full suite nếu có.
- Fixture có cleanup, không share global mutable session/tests; DB test production-specific nên dùng PostgreSQL thật (có thể Testcontainers).
- External API mock phải phản ánh contract thật; ít nhất một integration contract test nếu rủi ro lớn.
- Không sửa implementation chỉ để làm snapshot test qua bằng cách xóa assertion.
- Khi không chạy được: report `NOT RUN` + lý do + lệnh kiểm tra, **không bịa PASSED**.

Nguồn: https://docs.pytest.org/en/stable/reference/fixtures.html

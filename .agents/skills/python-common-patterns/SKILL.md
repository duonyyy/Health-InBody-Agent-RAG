---
name: python-common-patterns
description: Hướng dẫn AI coding agent thiết kế, triển khai, review và refactor Python backend/FastAPI/worker bằng các common patterns thực dụng (DI, Service Layer, Repository, Unit of Work, Strategy, Adapter, async, retry, idempotency, outbox). Dùng khi viết code Python, thay đổi kiến trúc, kiểm tra transaction/concurrency, tổ chức module hoặc xây nền tảng backend dùng chung. Luôn ưu tiên giải pháp nhỏ nhất, bằng chứng từ codebase và kiểm thử thay vì áp dụng mọi pattern.
license: MIT
compatibility: Python 3.11+; áp dụng cho FastAPI, SQLAlchemy 2.x, pytest khi dự án có các thư viện này. Các tài liệu tham khảo và ví dụ cục bộ không yêu cầu truy cập mạng khi đọc.
metadata:
  version: "1.0.0"
  language: vi
  category: backend-engineering
---

# Python Common Patterns — hướng dẫn tác nghiệp cho AI Coding Agent

## Mục tiêu

Giúp dự án Python dễ hiểu, dễ kiểm thử và đủ tin cậy mà KHÔNG biến thành framework nội bộ. **Chỉ áp dụng pattern khi có vấn đề hoặc yêu cầu cụ thể.** Không đổi kiến trúc chỉ vì có lựa chọn khác.

## Khi nào kích hoạt

- User yêu cầu viết/đánh giá/refactor Python, FastAPI API, worker, integrations, module dùng chung.
- Có vấn đề coupling, unit tests khó, transaction xuyên nhiều thao tác, async I/O, retry, lỗi tạm thời.
- User cần thiết kế Repository, Service Layer, UoW, Strategy, Adapter, Outbox/Inbox, idempotency.

## Trình tự bắt buộc (đọc ít, làm đúng)

1. **Khảo sát repo trước**: đọc `pyproject.toml`/requirements, Python version, module tree, API routes, session/DB lifecycle, tests, transaction, broker, CI. Không tuyên bố đã đọc file nào nếu chưa đọc.
2. **Xác định nhu cầu**: tóm tắt mục tiêu, constraint, invariant, phạm vi. Nêu rõ bằng chứng cho issue hiện tại; phân biệt bug, risk chưa chứng minh, cải tiến tùy chọn.
3. **Chọn giải pháp tối thiểu**: đối chiếu bảng quyết định dưới đây. Ưu tiên hàm, module, `Protocol`, `dataclass`, context manager, framework có sẵn trước class/hierarchy mới.
4. **Xác định ownership**: ai khởi tạo resource; ai commit/rollback; retry ở tầng nào; ai ack message; idempotency key/unique constraint ở đâu.
5. **Triển khai nhỏ, theo feature**: tránh refactor diện rộng ngoài phạm vi. Đảm bảo backward compatibility hoặc mô tả migration.
6. **Viết/chạy test liên quan**: happy path, lỗi, rollback, duplicate, concurrency khi cần. Không báo "passed" nếu chưa chạy; nếu thiếu runtime nêu rõ blocker và lệnh cần chạy.
7. **Báo cáo**: danh sách file đổi, pattern dùng + lý do, pattern cố ý không dùng, hành vi có bằng chứng, kết quả lệnh kiểm tra, rủi ro còn lại.

## Bảng chọn pattern — không tự động bật tất cả

| Khi gặp | Ưu tiên | Đừng làm |
|---|---|---|
| Route lẫn business logic | Service function/Service Layer | Chia 5 tầng chỉ để CRUD |
| Dependency khó mock | FastAPI `Depends` ở HTTP boundary; constructor DI ở phần khác | Service import trực tiếp `Depends` |
| Query lặp/DB truy cập phức tạp | Repository nhỏ gắn với feature | `GenericRepository[T]` khổng lồ |
| Một use case ghi nhiều bảng | 1 transaction boundary, có thể dùng UoW | Mỗi repository tự commit |
| Nhiều provider có cùng hành vi | `Protocol` + Adapter/Strategy | Abstract base class cho đúng 1 implementation |
| Chọn loại xử lý hữu hạn | Dict dispatch / function | Factory hierarchy |
| Nhiều tác vụ I/O độc lập | `TaskGroup` với giới hạn concurrency | Dùng chung `AsyncSession` giữa task |
| External call lỗi tạm thời | Timeout + bounded retry/backoff + jitter | Retry vô hạn hoặc retry write không idempotent |
| Cần DB update và publish message bền vững | Transactional Outbox khi thực sự cần | `commit()` rồi `publish()` coi như atomic |
| Consumer nhận trùng | Inbox/unique key + side-effect trong cùng transaction | Redis TTL cache thay thế unique DB constraint cho critical writes |
| Workflow xuyên nhiều service và cần compensation | Saga theo nghiệp vụ | Dùng Saga cho CRUD trong một DB |

## Luật chặn lỗi nghiêm trọng

- Giao dịch DB có **một owner rõ ràng**; `commit`/`rollback` tại boundary, không commit ẩn trong repository. Transaction nên ngắn; không giữ transaction DB trong lúc gọi HTTP/LLM lâu.
- `Session` không thread-safe; `AsyncSession` không dùng đồng thời giữa nhiều asyncio tasks. Session per request / per worker job / per task.
- `async def` không làm lời gọi blocking biến thành nonblocking. Dùng async driver hoặc đưa blocking work ra thread/process phù hợp.
- Idempotency của thao tác quan trọng phải được bảo đảm bởi thiết kế và durable constraint/atomic state transition; retry + timeout + duplicate có thể cùng xảy ra.
- Outbox có thể tạo **at-least-once** delivery; consumer phải xử lý duplicate. Saga không thay thế ACID nội bộ và không cung cấp atomic transaction toàn hệ thống.
- Không retry lỗi validation, auth, permission, integrity constraint thường trực. Không nuốt `CancelledError`.
- Không log secrets, access token, PII. Không thay đổi control bảo mật khi thiếu evidence.
- Không thêm package / dependency / queue / Redis / Kafka chỉ vì skill nhắc đến.
- Không áp đặt Clean Architecture, DDD, CQRS hoặc microservices mặc định.
- Không dùng blanket `except Exception: pass`, không gọi `time.sleep` trong async code.

## Tài liệu tham khảo — chỉ đọc phần phù hợp

| Chủ đề | Tài liệu |
|---|---|
| Pythonic, tối giản, typing | [references/pythonic-principles.md](references/pythonic-principles.md) |
| Package theo feature | [references/project-structure.md](references/project-structure.md) |
| DI và boundaries | [references/dependency-injection.md](references/dependency-injection.md) |
| Repository | [references/repository-pattern.md](references/repository-pattern.md) |
| Transaction / UoW | [references/unit-of-work.md](references/unit-of-work.md) |
| Service Layer | [references/service-layer.md](references/service-layer.md) |
| Factory / Strategy / Adapter | [references/factory-strategy-adapter.md](references/factory-strategy-adapter.md) |
| Async / concurrency | [references/async-concurrency.md](references/async-concurrency.md) |
| Errors / validation | [references/error-handling.md](references/error-handling.md) |
| Timeout / retry / breaker | [references/reliability-patterns.md](references/reliability-patterns.md) |
| Outbox / Inbox / Saga | [references/messaging-patterns.md](references/messaging-patterns.md) |
| Testing | [references/testing-patterns.md](references/testing-patterns.md) |
| Acceptance / review | [references/acceptance-checklist.md](references/acceptance-checklist.md) |
| Nguồn gốc, API chính thống | [references/sources.md](references/sources.md) |

## Ví dụ chạy được

- `examples/fastapi-service/`: CRUD tối giản theo feature, `Depends` ở boundary, Service + Repository, transaction do service quản lý, HTTP errors, tests.
- `examples/background-worker/`: idempotent consumer demo SQLite, atomic inbox + effect, duplicate no-op. KHÔNG tự nhận là Kafka/RabbitMQ production worker.
- `examples/snippets/`: Strategy và bounded retry ví dụ độc lập.

## Output format khi agent thực thi

```text
PHẠM VI: ...
EVIDENCE: [file:line hoặc test kết quả] ...
QUYẾT ĐỊNH: pattern nào, tại sao, phương án nhỏ hơn đã xét
IMPLEMENTATION: files changed ...
TEST: lệnh, pass/fail/not run, bằng chứng
RỦI RO CÒN LẠI: đã xác minh / chưa xác minh / optional
KẾT LUẬN: READY / BLOCKED (chỉ BLOCKED khi có P0 có bằng chứng)
```

**Nguyên tắc kết thúc:** Đạt acceptance criteria và không có P0 được chứng minh → **READY FOR IMPLEMENTATION / READY FOR MERGE** theo phạm vi; dừng vòng lặp review vô hạn.

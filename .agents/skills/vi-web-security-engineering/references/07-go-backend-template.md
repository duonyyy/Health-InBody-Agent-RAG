# 07 — Hướng dẫn vận dụng cho Go feature-first backend/template

Dành cho codebase có `internal/app`, `internal/platform`, `internal/modules`, `internal/shared`; không ép cấu trúc sang `domain/application/infrastructure/presentation` nếu repo không theo cách đó.

## Phân trách nhiệm

```text
internal/
  app/                    # DI/bootstrap, nối HTTP middleware, services, configs
  platform/
    httpserver/           # HTTP transport, limits, recovery, headers, CORS
    persistence/          # DB pool, transactions (không quyết định quyền domain)
    cache/                # cache business; không thay thế secure session store
    storage/              # Local/S3/MinIO adapters, file safety
    observability/        # logging/tracing, redaction
    messaging/            # transport Kafka/RabbitMQ, safe failure metadata
  modules/
    identity/             # nếu app thực sự có auth: auth, session, permission
    order/ ...            # authorization theo resource ở use case/queries
  shared/                 # generic errors/pagination; giữ nhỏ
```

## Các quyết định quan trọng

1. **Middleware wiring:** `Recovery`/`RequestID`/`BodyLimit`/`SecurityHeaders`/CORS/Auth chỉ có hiệu lực nếu đăng ký trên đúng handler chain. Test HTTP API ở composition root, không chỉ unit test factory middleware.
2. **Request body:** giới hạn stream đọc `r.Body` theo từng loại endpoint; `MaxHeaderBytes` không phải body limit. Kiểm tra context deadline, client cancel và upload paths.
3. **Authentication:** để nghiệp vụ identity (tài khoản/session) trong module; `platform/httpserver` chỉ xử lý generic transport adaptation nếu có interface phù hợp, không phụ thuộc sâu vào module gây import cycle.
4. **Authorization:** `RequirePermission` tại route không thay thế owner/tenant checks trong use case/repository. Dùng context chứa principal đã verify, đừng nhận tenant ID qua header trống.
5. **Redis:** cache cho giảm tải DB không thay thế session revocation/idempotency correctness; chọn Redis/Postgres theo semantics, không ép cả hai vào mỗi request.
6. **K8s health:** startup/liveness/readiness probes phải khớp router và port sau wiring; không truyền raw `err.Error()` trong public response.
7. **Compose:** localhost binding cho dependencies của local app khi host cần access; prod dùng network/credential policy khác.
8. **SSRF:** chỉ thiết kế outbound HTTP client an toàn cho URL không tin cậy khi có use case. Internal API calls qua config nên giữ được internal connectivity.
9. **RLS:** nếu app multi-tenant dùng PostgreSQL RLS, `SET LOCAL` chỉ có giá trị trong transaction và chính sách DB mới enforce; helper Go không đủ.
10. **Outbox:** là transaction/messaging reliability; không đưa vào security foundation nếu luồng nghiệp vụ chưa cần.
11. **Validation:** dùng stdlib hoặc thư viện phù hợp tại boundary/DTO; không nhất thiết có `internal/shared/validation`.
12. **CI:** cân bằng `go test`, `-race`, `go vet`, `govulncheck`, gitleaks, SAST. Ghi version của tool và cách xử lý false positives.

## V1 baseline với scaffold chỉ có health routes

Ưu tiên theo **sự tồn tại trong repo** và deployment mục tiêu:

- Public health response redaction.
- K8s probes đúng route (nếu manifests được dùng).
- HTTP body limits được wire (trước khi có untrusted body-consuming endpoints).
- Non-root runtime, local service network scoping.
- Basic dependency/secret scanning trong CI.

**Không tự khởi tạo:** JWT/OIDC/refresh rotation, RBAC, RLS, CSRF, CSP, outbound SSRF firewall, Outbox, auditing pipeline. Hãy ghi trigger khi chúng bắt buộc (identity/use case/browser cookies/multi-tenant/untrusted URLs/business events...).

## Regression test gợi ý

`tests/unit/` cho primitive; `tests/integration/` cho DB/Redis; `tests/e2e/` cho app router/wiring/probes. Tôn trọng conventions thực tế nếu codebase có layout khác; không tái cấu trúc tests chỉ vì sở thích.

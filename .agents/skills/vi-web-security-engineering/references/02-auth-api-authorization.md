# 02 — Authentication, Authorization & API Security

Chỉ kiểm tra các cơ chế liên quan đến surface đang có hoặc được yêu cầu. Dùng OWASP API Top 10 (2023) để định hướng; không điền 10 lỗ hổng khi app không có endpoint tương ứng.

## A. Kiểm kê API thực tế

- Liệt kê routes + method + handler + nguồn đăng ký + middleware chain + loại public/protected + dữ liệu đọc/ghi.
- Nếu OpenAPI/Swagger có, so thực với router; phát hiện endpoint không trong spec, deprecated và admin/debug APIs.
- Cập nhật bảng:

| Method/path | AuthN | AuthZ đối tượng | Input schema | Rate/body limit | Evidence |
|---|---|---|---|---|---|
| `/...` | public/session/bearer | policy + owner/tenant | validation | configured/unverified | file:line |

## B. Authentication

Với hệ thống đang dùng auth, kiểm tra:

- Local password: thuật toán chuyên dụng như Argon2id/bcrypt qua thư viện đáng tin, cost phù hợp; không plain SHA-256; không log mật khẩu.
- Login: chống enumeration bằng thông báo phù hợp, rate/abuse control theo threat model, account recovery bảo mật, MFA cho luồng nhạy cảm khi yêu cầu.
- JWT: verify signature **và** thuật toán được cho phép, `iss`, `aud`, `exp`, `nbf` khi áp dụng; key rotation; không tin claims từ token chưa verify; thu hồi theo threat model. Không dùng decode-only.
- OAuth2/OIDC: Authorization Code + PKCE, `state`, `nonce` khi phù hợp, redirect URI allowlist, xác thực issuer/audience, không rò rỉ code/token vào logs.
- API key: lưu an toàn, phạm vi quyền, rotation, tránh truyền trên query string.
- Cookie/session: `Secure`, `HttpOnly`, `SameSite` phù hợp, TTL + logout invalidation + session fixation defense, kiểm tra CSRF khi ambient cookie credentials.
- Refresh: nếu có refresh tokens thì đánh giá rotation/reuse handling và đồng thời cạnh tranh; không bắt scaffold tự triển khai refresh family.
- Service-to-service: auth thực, không chỉ tin nội bộ hoặc forwarded headers; TLS/mTLS khi môi trường cần.

**Test âm tính:** thiếu token, signature sai, algorithm không được phép, hết hạn, revoked, sai audience, logout/rotation khi dùng cơ chế đó. Không viết test cho cơ chế không tồn tại và chưa yêu cầu.

## C. Authorization

Cần đánh giá ở **ba lớp**, không chỉ một middleware:

1. Function/route: có giới hạn actor với chức năng không?
2. Object-level: tài nguyên cụ thể có thuộc owner/tenant hoặc actor có grant không?
3. Property-level: có thể đọc/sửa field nhạy cảm qua DTO/ORM mass assignment hoặc over-fetch không?

Mọi `id` trong path/query/body có thể bị sửa; UUID khó đoán không thay thế quyền truy cập. Đặc biệt kiểm tra các đường `list`, `batch`, `search`, `export`, `update`, `delete`, jobs.

**Deny by default:** khi chưa xác minh principal/quyền thì từ chối ở protected route, nhưng không áp middleware toàn cục làm hỏng health/public endpoints.

**Tenant isolation:** có thể thực thi ở service/repository hoặc PostgreSQL RLS. Không bắt buộc có RLS khi DB scoping đúng theo thiết kế. Nếu dùng RLS, kiểm tra policies, DB role không bypass RLS, transaction-local tenant context, pooling, CRUD và migrations thực tế.

## D. Các rủi ro API còn lại

- API1 BOLA: thay resource ID/batch IDs, xác minh ownership tại điểm dữ liệu.
- API2 Broken Auth: bypass verify/replay/brute-force/session.
- API3 BOPLA: mass assignment, overexposure dữ liệu không được cấp quyền.
- API4 Resource Consumption: unbounded pagination/query/depth/body/timeout/concurrency.
- API5 BFLA: user gọi admin/support endpoints.
- API6 Sensitive Business Flows: automation/abuse dù requests hợp lệ.
- API7 SSRF: user-supplied URLs, redirect, DNS rebinding/dial checks.
- API8 Misconfiguration: error detail, CORS (không phải auth), debug, defaults.
- API9 Inventory: shadow/versioned/deprecated endpoints không được bảo vệ.
- API10 Unsafe Consumption: third-party JSON/webhook/file, validate response, signature/replay when relevant.

## E. WebSocket/worker/webhooks

- WebSocket handshake: token auth, **Origin** policy khi cookie/browser context, connection lifecycle, per-message permission và size limits, không tin headers do client tự ghi.
- Worker: message signing/ACL/trusted broker hoặc xác minh domain context; idempotency/replay theo workflow, không coi queue header `x-tenant-id` là sự thật.
- Webhook: xác thực chữ ký trên raw body theo quy định provider, anti-replay/correct idempotency, giới hạn body và delivery retries.

## F. Kiểm chứng

- Lập test matrix: anonymous, owner, non-owner, same-tenant different-role, cross-tenant, admin, malformed input.
- Unit test kiểm tra policy logic; integration/e2e kiểm tra **route wiring + query scoping**.
- Scanner phát hiện một endpoint thiếu middleware không đủ chứng minh bypass: cần kiểm tra global middleware, gateway và service guard.

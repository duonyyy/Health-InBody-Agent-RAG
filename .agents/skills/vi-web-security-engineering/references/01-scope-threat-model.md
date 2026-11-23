# 01 — Phạm vi, bản đồ kiến trúc và threat model

## Điều kiện kích hoạt

Đọc trước audit toàn repo, review security model, xác định release gate, hoặc khi tìm nguồn của một input đáng ngờ.

## A. Thu thập thông tin dựa trên chứng cứ

Tìm: `README`, `go.mod`, `package.json`, `pyproject.toml`, routes/controllers, `cmd/*`, `internal/app`, Dockerfile/Compose, K8s, reverse proxy, workflow CI, migrations, middleware, worker/queue handlers.

Ghi riêng **đã xác minh / giả định / chưa biết**:

| Trường | Câu hỏi |
|---|---|
| Mục đích repo | Scaffold/libraries hay app đang phục vụ khách hàng? |
| Surface | Browser SPA/SSR, REST, GraphQL, gRPC, WS, webhook, worker, CLI? |
| Deployment | Public Internet, internal, local; edge/proxy; TLS termination? |
| Assets | PII, tiền, session, token, tenant data, API keys, filesystem, CI credentials? |
| Actors | Anonymous, user, admin, tenant khác, third-party, insider, CI PR author? |
| Security boundary | Client→API, API→DB, API→queue, worker→DB, CI→deploy, service→external URL? |
| Controls thực | Authenticate/authorize ở đâu, rate limit ở đâu, data scoping ở đâu? |
| Release contract | Cần bảo vệ những route và workflows nào? Có quy tắc cứng nào? |

**Không mặc định app public khi chỉ nhìn thấy `:8080` trong source.** Địa chỉ bind là dấu hiệu, không phải bằng chứng route Internet-reachable. Chú ý `docker-compose.yml` và deployment manifest có thể chỉ dùng local.

## B. Lập bản đồ đường đi và ranh giới tin cậy

Với mỗi boundary, ghi theo cấu trúc:

`Nguồn chưa tin cậy → parser → authentication → authorization → business service → sink → dữ liệu/tác động`

Ví dụ:

- Request HTTP `/orders/{id}` → bearer token → principal → `GetOrder(id)` → SQL `SELECT ... WHERE id = ?` → dữ liệu chủ sở hữu. Nếu không có owner/tenant check, cần truy vết xem guard được áp dụng trước hay ở repository.
- Webhook bên ngoài → xác thực chữ ký → replay/idempotency handling → ghi trạng thái → publish event. Thiếu bước nào, hậu quả là gì?
- PR từ fork → Actions trigger → checkout code từ PR → shell `run` + `secrets.*` → rủi ro chiếm credentials. Cần xét `permissions` và `pull_request_target` chính xác.

## C. Security invariants

Viết 3–8 bất biến thực sự quan trọng, mỗi bất biến phải có enforcement hoặc được đánh dấu chưa được thực thi:

1. Chỉ principal đã xác minh được truy cập endpoint riêng tư.
2. Mỗi hành động sửa dữ liệu kiểm tra quyền với đối tượng cụ thể.
3. Tenant A không xem/sửa dữ liệu Tenant B qua mọi read/write/query path, nếu ứng dụng multi-tenant.
4. Secret không xuất hiện trong HTTP response/log/event/public artifact.
5. Request/file/queue payload không được tiêu thụ vượt budget đã xác định.
6. Job/worker không tin tenant/user ID trong header do client tự đặt.
7. CI không thi hành mã từ nguồn không tin cậy với credential quyền cao.
8. Mỗi luồng đăng nhập/session thỏa chính sách đã chọn.

Tránh ghi những khẩu hiệu không thể kiểm chứng kiểu “system tuyệt đối an toàn”.

## D. Tạo abuse paths

Mỗi path gồm: `Attacker goal`, `attacker capabilities`, `entry point`, `precondition`, `control(s)`, `exploit hypothesis`, `impact`, `evidence`, `unknowns`.

Chỉ chọn các đe dọa có đường đi hợp lý; tránh hàng chục mục trùng lặp và false-positive.

**Severity** theo impact + likelihood + guard; **Priority** theo phát hành/nghiệm thu. Ví dụ lỗi route K8s sai làm hệ thống không lên khi dùng manifest đó là deployment blocker, nhưng không phải mặc nhiên CWE/exploitable DoS do kẻ tấn công.

## E. Không tạo chính sách tự phát

Nếu repo có `SECURITY_MODEL.md`, đọc để hiểu phạm vi, các quy tắc đã được chấp nhận; vẫn xác minh code và kiểm tra policy có lỗi thời. Không tự tạo/sửa `SECURITY.md` (file GitHub dùng làm disclosure policy). Chỉ tạo/sửa `SECURITY_MODEL.md` nếu MODE và quyền ghi cho phép.

## F. Quy tắc với scaffold

- `internal/modules/identity` chưa tồn tại: **không có điểm để bypass** nếu chưa có protected business routes.
- Nếu template cam kết có sẵn identity module runnable mà thiếu: `DOCUMENTED_CAPABILITY_GAP` hoặc `MISSING_REQUIRED` theo acceptance contract, chứ không tự động thành P0.
- Những tính năng yêu cầu logic nghiệp vụ (RLS/approval/reconciliation/outbox) chỉ đánh giá khi use case có ràng buộc đó.

## G. Kết quả tối thiểu

- Tên repo, phiên bản/ngày, scope, môi trường và bất định.
- Sơ đồ chữ 5–15 dòng hoặc bảng boundary ngắn.
- Danh sách asset + threat paths có bằng chứng.
- Danh sách security invariants và nơi enforce.
- Bảng “In scope / Out of scope / Conditional”.

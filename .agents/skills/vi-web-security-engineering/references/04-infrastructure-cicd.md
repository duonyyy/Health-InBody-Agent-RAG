# 04 — Docker, IaC, Kubernetes, CI/CD và chuỗi cung ứng

## 1. Xác định môi trường, đường phơi lộ

Phân biệt file ví dụ, dev-only Compose, prod manifests, code release; không khẳng định host port public Internet chỉ từ `5432:5432` khi chưa biết firewall. Tuy nhiên bind `0.0.0.0` trong Compose là một default đáng làm an toàn hơn với dev stack.

## 2. Docker & Compose

- Runtime chạy non-root; xem `USER`, ownership của thư mục ghi, capability, read-only rootfs khi phù hợp.
- Multi-stage build, image nhỏ và được cập nhật, image scanning, không copy `.env`/private keys vào layers, `.dockerignore` phù hợp.
- Builder Go/Node runtime tương thích với `go.mod`/lockfile/target build; tránh downgrade làm mất API bảo mật.
- Port mappings chỉ publish khi cần; local DB/Redis có thể bind `127.0.0.1`, prod thường chỉ dùng private network.
- Credentials: không đưa sản phẩm thực vào Compose; secret runtime qua môi trường quản lý/secret store. Mật khẩu dev được đánh dấu dev-only và không được tái dùng.
- Rootless/non-root sửa xong cần **chạy container** để verify `id -u`, liveness, permission dữ liệu ghi.

## 3. Kubernetes

- Kiểm tra startup/liveness/readiness **đúng route/port thực tế**, trạng thái readiness phản ánh dependency, liveness không gắn cứng mọi phụ thuộc nếu gây restart loop.
- SecurityContext: `runAsNonRoot`, UID phù hợp, drop capabilities, privilege escalation, seccomp và filesystem khi có thể.
- ServiceAccount scope, RBAC, Secret references, namespace isolation, network policy, resources/limits, ingress/TLS.
- `Pod` probes phải kiểm tra bằng integration test/config validation, không đoán 404 nếu route proxy rewrite hợp lệ.
- Không đưa wildcard RBAC ra P0 trừ khi quyền mở đường cho exploit ảnh hưởng asset thực.

## 4. Terraform/Helm/CloudFormation

- IAM quyền tối thiểu và trust relationships; public exposure của storage/DB; encryption, secrets/state access; version/source pinning.
- Terraform state có thể chứa secrets; không in state vào report, quản lý backend/permission/encryption.
- Kubernetes/Helm chart values và manifest render: giá trị tại deployment mới là cấu hình hiệu lực.
- Tool gợi ý khi có sẵn: `trivy config`, `checkov`, `kube-linter`, `cfn-lint`/`cfn-nag`. Kết quả scan phải được triage bằng ngữ cảnh.

## 5. GitHub Actions — đường tấn công cụ thể

Phải đọc `.github/workflows/*.yml`, reusable actions/workflows, `action.yml`, scripts từ workflow, và nếu workflow chạy code PR thì cả những file config PR kiểm soát (`Makefile`, `AGENTS.md`, `CLAUDE.md`...).

Kiểm tra:

1. **Pwn request:** `pull_request_target` hoặc workflow quyền cao checkout/run **fork PR code**; bám theo token/secrets thật.
2. **Expression injection:** `${{ github.event... }}` dữ liệu do attacker kiểm soát **nội suy vào shell `run:`**, phân biệt `if:`/`with:`/job env. Dò nguồn từng giá trị, không flag mọi expression.
3. **Issue comment commands:** comment trigger có thể chạy lệnh quyền cao khi chưa kiểm tra actor/permission.
4. **Credential escalation:** PAT/deploy key/cloud OIDC token tới steps chạy mã không tin cậy.
5. **Supply chain:** third-party actions/reusable workflows quyền cao không pin SHA hoặc không đủ trust; first-party `actions/*` theo tag không mặc nhiên là exploit.
6. **Runner/cache/artifacts:** self-hosted runner và artifact restore từ untrusted PR làm nhiễm bẩn các job có secrets.
7. **Prompt-injection trong CI có Agent:** file từ PR điều khiển lời nhắc và tool execution có secrets/permissions cao.

**Định dạng finding GitHub Actions:** attacker không có write permission → trigger gì → payload đi vào field nào → bước thực thi nào → credential/permissions nào bị ảnh hưởng → mitigation tối thiểu. Nếu chưa dựng được chuỗi hoàn chỉnh, gắn `NEEDS_VERIFICATION`.

## 6. Phân loại lỗi vận hành và bảo mật

- Probe route mismatch: lỗi độ sẵn sàng/deployment, có thể blocker khi dùng manifest, nhưng không phải exploit do attacker nếu không có vector.
- Container root: hardening quan trọng, không mặc định có container escape.
- Redis/Postgres local open interface: exposure risk cần ràng buộc theo host, network, auth.
- Kafka/Redis TLS: yêu cầu khi đi qua mạng không tin cậy hoặc chuẩn nội bộ áp dụng; không tự bật mọi kết nối dev local và làm hỏng tests.
- Không có Outbox: event consistency/reliability, không phải security vulnerability nếu không có security invariant liên quan.

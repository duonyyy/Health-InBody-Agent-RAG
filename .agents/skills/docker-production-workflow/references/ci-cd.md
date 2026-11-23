# Docker Development, Testing và CI/CD

## Mục tiêu

Pipeline nhanh nhưng an toàn: lint/test ứng dụng trước → Dockerfile/Compose checks → build cache → scan → smoke test nếu khả thi → publish/deploy ở workflow riêng được cấp quyền rõ ràng.

## CI Pull Request (mặc định không push)

1. `go test ./...` với Go version từ `go.mod`.
2. `docker buildx build --check` cho Dockerfile khi builder hỗ trợ.
3. `docker compose config --quiet` khi Compose hợp lệ và các file secret/config cần thiết có mặt; không in toàn bộ config vào CI logs.
4. Docker Buildx với cache GHA, `push: false`.
5. Scan CVE hoặc Docker Scout theo policy tổ chức, phê duyệt false positives thay vì tắt kiểm tra.
6. Smoke test qua một môi trường CI tách biệt, cấp secret giả và dependencies test. Không kết nối staging/production database ở PR.

Sử dụng `assets/github-actions.example.yml` như template; workflow PR không yêu cầu registry credentials hay deployment access. Đặt tại `.github/workflows/docker-ci.yml`, chỉnh path và matrix theo code thật.

## Runtime smoke test và integration test

- Image `ENTRYPOINT` phải có thể kiểm thử bằng command rõ; một số binary cần `--help` hoặc subcommand `healthcheck`.
- Không dùng `curl` trong distroless image để probe. Probe từ host/container test riêng khi cần.
- Test worker consumption với broker thật trong CI chỉ khi repo có consumer integration tests.
- Test Go API nhận SIGTERM và drain request in-flight; worker xử lý ack/requeue an toàn, không để duplicated side effects.
- Kiểm tra `health`/`readiness` riêng, networking nội bộ Compose, persistence khi restart **trong môi trường test cô lập**.
- Không xóa Docker resources bên ngoài scope CI; CI cleanup nếu cần chỉ xử lý tài nguyên do job sinh ra và đã kiểm tra nhãn/project.

## Cache và reproducibility

- Dockerfile copy module manifest trước source; cache mount cho Go packages/build.
- GitHub Actions: `docker/setup-buildx-action` + `docker/build-push-action` với `cache-from: type=gha`, `cache-to: type=gha,mode=max` khi quyền và quota cho phép.
- Phiên bản workflow actions nên pin commit SHA sau khi được tổ chức xét duyệt (template minh họa dùng release tags).
- Với release image: pin base digest, scan/tag đúng immutable digest, SBOM/provenance và ký image theo policy; dùng environments và approvals.
- Secrets cho build phải qua `secrets`/`ssh` input của action nếu thực sự cần; không dùng `build-args` để chuyển token.

## Tiêu chí hoàn tất CI

- Không có permission ghi/deploy dư trong PR.
- Không push image khi chưa được yêu cầu.
- Mỗi check có tiêu chí pass/fail và báo cáo log không lộ secret.
- Có chỉ dẫn để chạy kiểm tra tương đương local.
- Nếu Docker unavailable: báo “chưa verify runtime”, không tuyên bố pipeline đã chạy.

## Khác biệt dev/prod

- Dev: hot reload bằng bind mount, verbose logs, local test fixtures, loopback port mapping.
- Prod: immutable image, rollback theo image digest và DB migration plan, runtime non-root, secret manager, log/monitoring phù hợp, scan policy.
- Pipeline deploy **không** được tạo/tự kích hoạt nếu người dùng chỉ yêu cầu CI.

**Nguồn**: https://docs.docker.com/build/ci/github-actions/ ; https://docs.docker.com/build/ci/github-actions/cache/ ; https://docs.docker.com/build/ci/github-actions/attestations/ ; https://github.com/netresearch/docker-development-skill

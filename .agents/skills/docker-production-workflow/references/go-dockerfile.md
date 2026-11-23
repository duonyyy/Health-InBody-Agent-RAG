# Go Dockerfile — hướng dẫn triển khai production

## Mục tiêu và khảo sát

Trước khi thiết kế, xác định `go` trong `go.mod`, đường dẫn `./cmd/...`, OS/architecture đích, sử dụng CGO (SQLite, native lib), DNS/TLS, CA cert, time zone, file cấu hình, user ID và tín hiệu SIGTERM. Không tự đổi phiên bản Go hoặc image runtime làm phá ABI.

## Lớp build và cache

1. Tạo `.dockerignore` hạn chế context. Bỏ `.git`, `.env*` (ngoại lệ `.env.example` nếu cần), secret, key, IDE, bin, `node_modules`, test artifacts; **không** bỏ file được `COPY` yêu cầu.
2. `FROM --platform=$BUILDPLATFORM golang:<version>-bookworm AS build`; cân nhắc pin `@sha256` cho CI nghiêm ngặt; ghi quy trình cập nhật digest. Tránh dùng `latest`.
3. `COPY go.mod go.sum ./` trước `RUN --mount=type=cache,target=/go/pkg/mod go mod download`, rồi mới `COPY . .`.
4. Cache build `--mount=type=cache,target=/root/.cache/go-build`; cache mount giúp build nhanh nhưng không phải đầu ra cần được đóng gói.
5. Có thể đặt `ARG TARGETOS`, `ARG TARGETARCH` **trong build stage** và build với `GOOS=$TARGETOS GOARCH=$TARGETARCH`. Test image trên từng architecture. Không cố ép `CGO_ENABLED=0` nếu code phụ thuộc native.
6. Runtime stage không mang compiler, source, Go module cache; dùng distroless/static, scratch hoặc debian slim theo dependency. Distroless thiếu shell/curl: healthcheck phải qua binary hoặc thiết kế khác.
7. Dùng exec ENTRYPOINT, user không phải root; hỗ trợ SIGTERM trong Go (`signal.NotifyContext`, `http.Server.Shutdown`, drain worker) và đủ thời gian grace period.

## Mẫu

- Xem `../assets/Dockerfile.go` (tương đối theo thư mục `references/`).
- Nhờ agent xác minh `APP_PATH`, Go version, CGO, port, config/CA và kiểm thử binary trước khi copy vào root dự án.
- Nếu binary worker riêng: build cùng Dockerfile với `--build-arg APP_PATH=./cmd/worker` hoặc target riêng; chọn dựa trên chính repo.

## Không dùng mẫu dưới dạng mặc định trong mọi dự án

- **CGO**: nếu cần libc, dùng base runtime tương thích và copy dynamic libs đúng; đừng sử dụng `scratch` đơn giản.
- **Go private module**: dùng BuildKit secret mount/SSH mount, không dùng `ARG GITHUB_TOKEN` hoặc `ENV GOPRIVATE_PASSWORD` để đẩy credential vào history/logs.
- **TLS**: xác minh trust store của image và chứng chỉ dịch vụ.
- **Timezone**: dùng UTC nếu phù hợp; nếu app phụ thuộc zoneinfo, cung cấp zoneinfo có kiểm tra.
- **Filesystem**: nếu `read_only: true`, phải cấp `tmpfs` hoặc volume cho đường dẫn ghi dữ liệu chính xác.
- **Health**: lệnh `app healthcheck` chỉ hoạt động khi app thật sự triển khai subcommand tương ứng; không tạo healthcheck giả `exit 0`.

## Kiểm chứng thực tế

```bash
bash <skill-dir>/scripts/check-dockerfile.sh Dockerfile
docker buildx build --check -f Dockerfile .   # nếu Buildx hỗ trợ
docker build -f Dockerfile -t app:check .       # chỉ trên context được phép
docker image inspect app:check --format '{{.Config.User}}'
docker image inspect app:check --format '{{.Architecture}}/{{.Os}}'
```

Nếu có quyền chạy test, thử command `healthcheck`, một request HTTP thực, signal SIGTERM và startup khi dependency chưa sẵn sàng. Ghi lại các thông số đo được, không tự ước lượng.

### Ví dụ `.dockerignore` (điều chỉnh theo repository)

```dockerignore
.git
.github
.vscode
.idea
.env
.env.*
!.env.example
**/*.pem
**/*.key
**/id_rsa
**/id_ed25519
node_modules
.venv
__pycache__
coverage
*.out
bin
```

**Tài liệu nguồn**: https://docs.docker.com/guides/golang/ ; https://docs.docker.com/build/building/multi-stage/ ; https://docs.docker.com/build/cache/ ; https://docs.docker.com/build/building/secrets/ ; https://github.com/docker/skills/tree/main/skills/docker-build-strategies

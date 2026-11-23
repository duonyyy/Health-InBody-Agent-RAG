---
name: docker-production-workflow
description: "Skill Docker tiếng Việt dành cho AI Coding Agent, đặc biệt Go backend: khởi tạo Docker, tối ưu Dockerfile multi-stage/BuildKit, kết nối API-worker-PostgreSQL-Redis-broker bằng Compose, bảo vệ dữ liệu, hardening container và CI/CD. Dùng khi tạo, sửa, đánh giá, debug hay kiểm thử Dockerfile, compose.yaml, image, container hoặc pipeline Docker."
compatibility: "Cần Bash cho scripts; Docker Engine/Compose v2 cho kiểm tra ngữ nghĩa và runtime; có thể review tĩnh nếu không có Docker."
metadata:
  version: "2.0.0"
  language: "vi"
  scope: "docker-go-backend"
---

# Docker Production Workflow — quy trình Docker an toàn cho AI Coding Agent

> Skill tự chứa, viết lại theo tài liệu Docker và các Agent Skills tham khảo. **Không phải skill chính thức của Docker** và **không tự kích hoạt** các skill khác. Tất cả file đi kèm đều nằm trong thư mục này.

## 1. Khi nào sử dụng

- Docker hóa backend mới hoặc chuẩn hóa Dockerfile, `.dockerignore`, `compose.yaml`.
- Cải thiện tốc độ build/độ lớn image Go, multi-stage, BuildKit, Buildx, multi-platform.
- Kết nối API, worker, PostgreSQL, Redis và Kafka/RabbitMQ khi dự án thực sự dùng.
- Xử lý readiness, networking, startup, restart, dữ liệu volume, permissions.
- Kiểm toán bảo mật, CVE, SBOM, provenance, secret, CI GitHub Actions.
- Xử lý yêu cầu dọn dẹp/reset Docker mà có thể gây mất dữ liệu.

Không thay Docker Compose bằng Kubernetes nếu chưa được yêu cầu. Không xây framework Docker riêng.

## 2. Quy tắc bắt buộc (P0)

1. **Khảo sát trước khi sửa**: chỉ mở file liên quan (`go.mod`, `cmd/`, Dockerfile, Compose, env example, CI); xác định entrypoint, Go/CGO, cổng, health endpoint, nhu cầu lưu state và môi trường đích.
2. **Không xóa dữ liệu ngoài ý muốn**: cấm tự thực thi `docker compose down -v`, `docker volume rm/prune`, `docker system prune`, `docker builder prune`, `docker rm -f`, reset DB, xóa bind mount hoặc cleanup trên remote context. Yêu cầu phê duyệt cụ thể theo [data-safety](references/data-safety.md) trước mọi thao tác phá hủy. Không lách bằng shell, aliases hoặc script.
3. **Không tự gây gián đoạn**: trước khi `up`, `restart`, `stop`, `down`, `pull`, `push`, migrate hoặc recreate dịch vụ thực, xác định context/target, tác động và quyền chạy. Tránh thực hiện nếu chưa được phép.
4. **Không làm lộ bí mật**: không đọc/in `.env` thật, private key, token; không chạy `docker compose config` không có `--quiet` trong logs/chats. Không đưa secret vào `ARG`, `ENV` của build, image layer, workflow. Secrets build dùng BuildKit `--secret`/`--ssh`; runtime dùng secret manager hoặc Compose secrets khi phù hợp.
5. **Ít thay đổi nhất**: tái sử dụng cấu trúc cũ; không thêm DB/cache/broker khi không dùng; không refactor ngoài nhiệm vụ.
6. **Không nhận định quá mức**: phân biệt `tĩnh`, `Compose được kiểm tra`, `image build thành công`, `runtime smoke test thành công`, `đã kiểm thử triển khai thực`; không đồng nhất build pass với production-ready.
7. **Không hạ bảo mật để sửa lỗi**: không mặc định dùng root, privileged, Docker socket mount, chmod 777, host network hoặc vô hiệu hóa TLS.
8. **Không copy mù quáng tài nguyên mẫu**: `assets/` là template, phải khớp `cmd/api`, `cmd/worker`, Go version, CGO, env vars, migrations và liveness/readiness thực tế.

## 3. Chọn phần hướng dẫn theo yêu cầu

| Nhiệm vụ | Tài liệu cần đọc | Mẫu/kiểm tra |
| --- | --- | --- |
| Tạo/tối ưu Dockerfile Go | [go-dockerfile.md](references/go-dockerfile.md) | `assets/Dockerfile.go`, `scripts/check-dockerfile.sh` |
| Kết nối API, worker, DB/cache/broker | [compose-microservices.md](references/compose-microservices.md) | `assets/compose.example.yaml`, `scripts/check-compose.sh` |
| Bảo mật container và supply chain | [container-security.md](references/container-security.md) | `scripts/check-security.sh` |
| Build/test/CI | [ci-cd.md](references/ci-cd.md) | `assets/github-actions.example.yml` |
| Dọn dẹp, volume, reset, migration, rollback | [data-safety.md](references/data-safety.md) | Không có script phá hủy |
| Đánh giá chất lượng skill | `evals/scenarios.md` | Các tình huống Given/When/Then |

**Tác vụ kết hợp**: dự án chưa Docker hóa → nền tảng → Dockerfile → Compose → bảo mật → CI; nếu chỉ sửa Dockerfile thì không tạo Compose mới. Quy tắc an toàn dữ liệu áp dụng **mọi lúc**.

## 4. Quy trình triển khai

### A. Kiểm tra dự án (chỉ đọc)
- Xác định source tree tối thiểu, module Go, version trong `go.mod`, API và worker entrypoints, cần CGO không, thư mục ghi dữ liệu.
- Xem các file liên quan; không recursive scan thư mục dependencies/generated, không dump `.env`.
- Kiểm tra `docker context show`, `docker version`, `docker compose version` khi Docker khả dụng; không mặc định context là local.
- Nêu ngắn: phát hiện, file dự định đổi, rủi ro, lệnh kiểm tra an toàn và các phần cần phê duyệt.

### B. Thiết kế và sửa
- Dockerfile: builder/runtime tách riêng; Go module cache; `.dockerignore`; runtime non-root; base image đã xác minh và được kiểm soát phiên bản.
- Compose: chỉ services đang dùng; DNS qua service names; healthcheck đúng binary; `depends_on: service_healthy` nhưng ứng dụng vẫn cần retry/reconnect; named volumes cần thiết; không xuất port datastore ra host ngoài yêu cầu.
- Hardening: least privilege, quản lý secrets, read-only nếu tương thích, CVE scan, SBOM/provenance theo pipeline.
- CI: chạy test Go → build image với cache → Docker/Compose check → scan khi có tooling; PR không push/deploy, không cần credentials production.

### C. Xác minh theo tầng (không thay thế nhau)

```bash
# Chạy từ project root; thay <skill-dir> bằng đường dẫn tuyệt đối của skill
bash <skill-dir>/scripts/check-dockerfile.sh Dockerfile
bash <skill-dir>/scripts/check-compose.sh compose.yaml
bash <skill-dir>/scripts/check-security.sh Dockerfile compose.yaml

# Chỉ nếu Docker context đã được xác minh và người dùng đồng ý build:
docker buildx build --check -f Dockerfile .
docker build -t myapp:verification .
# Chỉ chạy smoke test nếu môi trường được phép và kế hoạch có kiểm soát.
```

Các script không xóa/restart/push; `check-compose` trả trạng thái **2** nếu thiếu Docker Compose, nghĩa là **chưa kiểm chứng ngữ nghĩa**. Script lint chỉ phát hiện một số mẫu tĩnh, **không chứng minh an toàn**.

### D. Báo cáo
1. File đã thay đổi và lý do.
2. Bằng chứng: lệnh, exit code, kết quả build/scan/smoke test thực tế; phần nào chưa chạy và vì sao.
3. Rủi ro bảo mật, dữ liệu, vận hành; yêu cầu phê duyệt nếu có.
4. Cách triển khai/rollback an toàn, không xóa volume.

## 5. Cách sử dụng mẫu

`assets/Dockerfile.go` dự kiến `./cmd/api`, `CGO_ENABLED=0`, distroless. Đổi `APP_PATH=./cmd/worker` cho worker nếu cùng mẫu tương thích. `assets/compose.example.yaml` dùng Docker Compose secrets **từ file có sẵn bên ngoài Git**, Go app cần hỗ trợ `DB_PASSWORD_FILE` và `healthcheck` subcommand — **không copy nếu ứng dụng chưa hỗ trợ**. Workflow CI cần đặt tại `.github/workflows/docker-ci.yml` rồi kiểm tra lại đường dẫn.

## 6. Nguồn cập nhật (tham khảo, không tự nạp)

- Docker official skills: https://github.com/docker/skills/tree/main/skills (project-foundations, build-strategies, compose-patterns, destructive-guardrails).
- Community security: https://github.com/sickn33/agentic-awesome-skills/tree/main/skills/container-security-hardening
- Community development: https://github.com/netresearch/docker-development-skill
- Docker Docs: https://docs.docker.com/build/ ; https://docs.docker.com/compose/
- Agent Skills spec: https://agentskills.io/specification

Nếu skill nguồn đã cài sẵn và phù hợp, có thể đọc **bổ sung**; không bắt buộc. Đối chiếu hướng dẫn với tài liệu chính thức và phiên bản Docker hiện tại trước khi áp dụng các tùy chọn mới.

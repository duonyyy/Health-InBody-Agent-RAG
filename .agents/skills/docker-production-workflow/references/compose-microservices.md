# Docker Compose — Go API, worker và hạ tầng

## Nguyên tắc

- `compose.yaml` là tên chính. Giữ mô tả dịch vụ tối thiểu và rõ trách nhiệm.
- Container gọi nhau bằng service name (`db`, `cache`, `broker`), không phải `localhost`; host port chỉ cho những thứ phải truy cập từ host, nên mặc định bind loopback.
- Cần `depends_on: condition: service_healthy` với dependency hỗ trợ healthcheck. **Không thay cho retry/reconnect** sau khi app đã chạy.
- Không lạm dụng `container_name`; Compose project name giúp tách namespace theo môi trường.
- Đối với PostgreSQL, healthcheck `pg_isready` không chứng minh schema migration xong. Nếu migration quan trọng, dùng migration job có cơ chế một-writer, kiểm tra lock và rollback.
- API và worker thường build riêng entrypoint (`cmd/api`, `cmd/worker`), có thể dùng chung Dockerfile theo build arg nếu phù hợp.
- Bảo vệ named volume của DB; `docker compose down` khác `docker compose down -v` (cái sau phá dữ liệu). Không dùng `down -v` để chữa lỗi mạng/migration.

## Chỉ thêm dịch vụ khi thật sự cần

| Dịch vụ | Ví dụ readiness | Lưu ý |
| --- | --- | --- |
| PostgreSQL | `pg_isready -U ... -d ...` | Không tương đương ứng dụng đã migrate |
| Redis | `redis-cli ping` | Cần điều chỉnh nếu bật auth/TLS |
| RabbitMQ | `rabbitmq-diagnostics -q ping` hoặc lệnh phù hợp version | `ping` không bảo đảm exchange/queue đã khai báo |
| Kafka KRaft | Lệnh/admin client đúng broker/image | Test `advertised.listeners`, client connection, ACL |
| Go API | `app healthcheck` hoặc probe qua HTTP từ công cụ phù hợp | Distroless không có shell/curl |
| Go worker | app-side heartbeat và queue connectivity | Không nên healthcheck luôn thành công |

**Không** tự động thêm cả Kafka lẫn RabbitMQ. Nếu hiện tại không cần broker, bỏ `broker` khỏi Compose và env.

## Networking và dữ liệu

- Network internal mặc định của Compose thường đủ; phân tách public/internal khi có đòi hỏi threat-model.
- Database/cache không xuất port `0.0.0.0` mặc định. Nếu phải debug từ máy, dùng `127.0.0.1:5432:5432` và có kiểm soát.
- Named volumes để giữ state, bind mounts cho hot reload dev; tránh share Docker socket.
- Redis chỉ nên persistent nếu cần durability; nếu Redis dùng làm cache thuần, làm rõ dữ liệu có thể mất khi restart.
- `read_only: true` và `tmpfs` tốt cho app không ghi xuống root FS; nhưng phải test logs/temp/config và file permissions trước.
- Quản lý `mem_limit`/CPU/PIDs/log rotation theo tài nguyên và tải thực tế; không sao chép giới hạn mẫu vô căn cứ.

## Secrets

- `env_file` hoặc `.env` không phải secret manager. Compose `secrets` có thể được khai báo từ file hoặc biến môi trường, được mount vào container tại `/run/secrets/...`.
- Ứng dụng phải biết đọc `_FILE` (ví dụ `DB_PASSWORD_FILE`) thì mẫu `assets/compose.example.yaml` mới chạy được.
- Không commit `secrets/` và không echo password ra màn hình. Với production, dùng secret manager/CI secrets chuyên dụng.
- Lệnh `docker compose config` thông thường in nội dung env đã nội suy. Luôn dùng `--quiet` khi xác minh; vẫn rà soát thông báo lỗi tránh vô tình chia sẻ bí mật.

## Thứ tự xác minh

1. `bash <skill-dir>/scripts/check-compose.sh compose.yaml`.
2. Xác định `docker context show`; kiểm tra named volume và đối tượng sẽ bị ảnh hưởng.
3. Với quyền chạy phù hợp: `docker compose build api worker`.
4. `docker compose up -d` chỉ sau khi biết scope/recreate effect, đã được cho phép.
5. `docker compose ps`; log giới hạn theo service (log vẫn có thể chứa PII/secret), xác minh DNS, DB connect, API smoke test, worker queue consume.
6. Kiểm tra reconnect sau khi DB/queue mất kết nối trên **môi trường test chuyên dụng**, không gây gián đoạn production.

## Migration / job một lần

- Tách migration thành job chạy trước khi nâng API (một job duy nhất, lock/transaction phù hợp). Các migration destructive yêu cầu kiểm tra backup, approval và kế hoạch rollback.
- `depends_on: service_completed_successfully` có thể hữu ích cho job chạy một lần trong Compose hỗ trợ, nhưng cần thử trên phiên bản thực tế.
- Không dùng `depends_on` như công cụ điều phối saga hoặc bảo đảm consistency dữ liệu phân tán.

**Nguồn**: https://docs.docker.com/reference/compose-file/services/ ; https://docs.docker.com/compose/how-tos/use-secrets/ ; https://github.com/docker/skills/tree/main/skills/docker-compose-patterns

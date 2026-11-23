# Docker Destructive Guardrails — bảo vệ dữ liệu và môi trường

## Quy tắc tuyệt đối

**Không tự thực thi lệnh gây mất dữ liệu hoặc gián đoạn môi trường dùng chung/production.** Đọc hiểu tác động của lệnh đầy đủ, bao gồm shell pipe, scripts, Makefile, CI job, aliases và Docker context. Có thể lập kế hoạch, giải thích và yêu cầu xác nhận nhưng không coi câu trả lời mơ hồ là phê duyệt.

## Phân loại và yêu cầu

| Mức | Ví dụ | Cách xử lý |
| --- | --- | --- |
| R0: chỉ đọc | `docker ps`, `docker images`, `docker volume ls`, `docker compose config --quiet`, `docker inspect` | Cho phép khi context/scope rõ; tránh xuất dữ liệu nhạy cảm |
| R1: tạo/build | `docker build`, `docker compose build`, `docker pull` | Xác định context, disk/network/CI impact, quyền thực thi; không auto trên production |
| R2: gián đoạn | `compose up -d` (recreate), `restart`, `stop`, `down`, migrate schema, image replacement | Nêu service, downtime, rollback; cần quyền triển khai/phê duyệt phù hợp |
| R3: phá hủy | `compose down -v`, `docker volume rm/prune`, `system prune`, `builder prune`, `rm -f`, xóa bind mount, DROP/TRUNCATE DB | Chặn theo mặc định, xin xác nhận *cụ thể từng mục* và backup/restore plan; từ chối nếu scope mơ hồ |

Lưu ý: `docker compose down` thường giữ named volumes nhưng vẫn làm dừng/xóa containers và networks; không được xem là vô hại đối với production. `docker compose down -v` xóa volumes của project không được khai báo external, có thể làm mất DB. `docker volume prune` nguy hiểm với volume có dữ liệu không gắn container.

## Quy trình trước lệnh R2/R3

1. Xác nhận `docker context show`, host/cluster, Docker project, service, env (`dev`, `staging`, `production`), dữ liệu liên quan.
2. Liệt kê tên chính xác image/container/volume/bind mounts bị ảnh hưởng; không dùng wildcards khi không cần.
3. Giải thích có thể mất dữ liệu hay gây downtime không. Đề xuất lựa chọn ít rủi ro trước.
4. Nếu cần hành động R3: có bản sao lưu **đã kiểm tra khả năng restore**, người duyệt và giới hạn phạm vi; không nhận câu “dọn tất cả đi” như phê duyệt production mặc định.
5. Khi đã duyệt: thực thi nhỏ nhất, quan sát kết quả, xác minh trạng thái; không chạy lặp lại lệnh thất bại nhiều lần mà không phân tích nguyên nhân.

## Ví dụ thay thế an toàn

- Lỗi mạng Compose: kiểm tra `compose ps`, network resolution, ports, health logs; không reset volumes.
- Lỗi PostgreSQL schema: kiểm tra version migration, migration state, logs và backup; không `DROP DATABASE`.
- Hết disk: thống kê image/cache/volumes và đề xuất targeted cleanup; không `system prune -a --volumes`.
- Không thể build: kiểm tra `.dockerignore`, Dockerfile, logs build (chú ý secrets); không phá toàn bộ builder cache.

## Ghi chú riêng cho script của skill

Ba script `check-*` chỉ **đọc cấu hình**; `check-compose` chạy `docker compose config --quiet` khi Docker CLI sẵn có; `check-security` có thể gọi Trivy scan image khi user chủ động cung cấp `--image`, có thể tải vulnerability DB. Không script nào chạy `down`, `prune`, `rm`, `push` hay `deploy`.

**Nguồn**: https://github.com/docker/skills/tree/main/skills/docker-destructive-guardrails ; https://docs.docker.com/reference/cli/docker/compose/down/ ; https://docs.docker.com/reference/cli/docker/volume/prune/

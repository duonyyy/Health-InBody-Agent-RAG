# WP-01 — Bằng chứng đóng gói Profile B (2026-11-05)

> **Bằng chứng lịch sử:** Profile B đã được rút cùng ngày theo quyết định mới. Hai container/image ứng dụng và bốn container hạ tầng test đã dừng được gỡ; ba volume wp01_* được giữ nguyên. Image/HTTP test bên dưới không chứng minh backend gộp đang chạy và không phải runbook để triển khai lại hai service.

## Quyết định và phạm vi

- Hai service lấy `contracts/` từ một build context ở repo root. Mỗi image chỉ chép `contracts/` và source của chính service; không mount hoặc import `backend/src`.
- Core API sở hữu PostgreSQL và memory persistence. Agent Service không cần `DATABASE_URL`, không import `persistence` và không recall Zep. Profile B không dùng Zep; hai API bộ nhớ ngoài của Core trả 501 sau xác thực, không ghi consent hoặc báo xóa cloud thành công.
- Không thay đổi runtime Profile A, corpus Qdrant, alias hoặc dữ liệu thật.

## Kết quả đã chạy

| Gate | Kết quả |
|---|---|
| Host Python 3.13, test độc lập Core API | 10/10 passed (`core-api/tests/test_packaging.py`) |
| Host Python 3.13, test độc lập Agent Service | 10/10 passed (`agent-service/tests/test_packaging.py`) |
| Baseline backend chọn lọc | 34/34 passed ở lượt WP-00/WP-01 trước; không chạy lại sau thay đổi lần này vì không sửa `backend/src` |
| Compose | `docker compose config --quiet` đạt với 5 file compose |
| Build | `docker compose -f docker-compose.microservices.yml build core-api agent-service` exit 0 |
| Image Python 3.11 | Core import các module cần thiết và `init_db()` trên SQLite tạm đạt; Agent import `main`, graph, memory helpers và `rag.splitter` đạt |
| HTTP trong container tạm, network cô lập | Core `GET /health` 200 với SQLite tạm; Agent `GET /` 200. Hai container tạm đã dừng và tự xóa |
| Whitespace/syntax | `git diff --check` exit 0; AST parse 5 entrypoint/module liên quan đạt |

## Chạy Profile B tích hợp trên volume test mới

Compose Core ban đầu dùng `postgresql://postgres@.../health_db`, khác user/DB của Compose hạ tầng và khiến SQLAlchemy tìm driver `psycopg` không có trong image. Đã sửa URL theo `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` của hạ tầng và ghi rõ driver `postgresql+psycopg2://`; probe trong Core image xác nhận driver. Hai Compose bind cổng host vào `127.0.0.1` cho lần chạy `AUTH_MODE=development`.

Lần chạy này dùng ba volume riêng `wp01_postgres_20261105`, `wp01_qdrant_20261105`, `wp01_valkey_20261105`; trước khi chạy không có container dự án hoạt động và Qdrant mới có 0 collection/alias. File cấu hình cục bộ `.env.profile-b.local` đã được gỡ cùng Profile B; volume test được giữ nguyên, không tự xóa dữ liệu.

| Kiểm chứng HTTP/runtime | Kết quả |
|---|---|
| PostgreSQL 16 | `pg_isready` đạt; `init.sql` tạo 13 bảng; sau hai request test có 1 `chat_sessions`, 4 `chat_messages` trên DB test |
| Core API → Agent Service | `POST /chat/complete` qua Core trên localhost: urgent trả `fast_path=urgent_safety`, BMI 72 kg/170 cm trả `fast_path=inbody_tools`, cả hai HTTP 200/status `ok`; Agent log ghi hai `POST /v1/agent/chat` 200 |
| Valkey | Agent health/log cho thấy kết nối cache đến `valkey-db:6379/0` |
| Embedding CPU | BGE-M3 local tải thành công, device `cpu`, dtype `float32`; Agent nhận vector 1024 chiều qua `embedding-api` |
| Qdrant | Agent gọi `qdrant-db:6333/collections` được HTTP 200; tạo collection mới `wp01_runtime_20261105` với schema/index của ứng dụng; upsert một vector synthetic 1024 chiều có ID ổn định được chấp nhận |

Trong lúc build/khởi động embedding, các container Core, Agent, PostgreSQL, Qdrant và Valkey dừng sạch cùng thời điểm không rõ nguyên nhân; đã khởi động lại trên chính các volume test và xác nhận sáu service chạy, embedding healthy. Chưa xác nhận được nguyên nhân dừng này; không coi một lần chạy là soak test.

**Còn thiếu:** Chưa tạo alias `nmk_chatbot_active` trỏ tới collection test và chưa chạy truy vấn vector qua Agent; không có corpus thật hoặc đánh giá chất lượng RAG/LLM. Thao tác `docker exec` tạo alias bị automatic approval review từ chối vì hết hạn mức sử dụng; hệ thống báo đây là lỗi review, không phải kết luận thao tác không an toàn. Không thử đường khác để vượt qua review. Sau khi review hoạt động lại, kiểm tra collection/alias/point count hiện tại trước khi tạo alias; chỉ thao tác trên volume test. Chưa test frontend, auth production hoặc luồng context của WP-02.

Không tái chạy Profile B từ báo cáo này: hai thư mục service, Compose và file env đã được gỡ. Lần thử lịch sử dùng `AUTH_MODE=development`, `LLM_PROVIDER=none`, chỉ bind localhost.

Nếu có consent hoặc dữ liệu Zep từ Profile A, không chuyển traffic xóa dữ liệu sang endpoint 501 của Profile B trước khi có phương án thu hồi/xóa riêng được kiểm chứng. Mã Zep legacy còn trong repository nhưng không có đường gọi runtime của Profile B và không có dependency SDK trong hai image.

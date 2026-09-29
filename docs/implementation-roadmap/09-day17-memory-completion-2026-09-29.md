# Hoàn thiện bộ nhớ Day17 — 2026-09-29

Trạng thái: **source-ready, chưa deploy**. Đây không phải nghiệm thu production hoặc đánh giá chất lượng y khoa.
Tài liệu này thay thế mô tả raw-chat continuity và lỗ hổng task owner trong báo cáo 08.

## Phạm vi và quyết định

| Ý tưởng | Đã nối trong source | Ranh giới |
|---|---|---|
| Ngắn hạn | Phiên UUID do server tạo, owner từ auth context, lưu/đọc history PostgreSQL dùng chung HTTP/Celery | Không dùng lịch sử hoặc user ID giả từ client; context hữu hạn |
| Dài hạn | Hồ sơ/goal/lần đo P1 giữ nguồn chuẩn; thêm fact pending → confirm → expire/delete | Chỉ sở thích, cần xác nhận riêng; chưa có bộ trích xuất fact y khoa |
| Sự kiện | Nhắc plan/check-in theo user, thời gian, source ID, trạng thái và goal version | Plan cũ không tự áp dụng lại; check-in không phải chứng minh hiệu quả điều trị |
| Tri thức chung | Qdrant giữ vai trò nguồn citation; kiểm tra admission ở API/worker/import | Không nạp profile/chat/Zep vào corpus chung; không thay collection đang phục vụ |

Zep không phải database nguồn chuẩn thứ hai. Chỉ sở thích đã xác nhận được mirror sau consent riêng;
không tự gửi transcript, câu hỏi đang hỏi, chỉ số hoặc bệnh sử lên cloud. Sở thích local vẫn vào composer khi Zep tắt.
Kết quả Zep chỉ xếp chọn fact ID; nội dung luôn đối chiếu fact còn hiệu lực của đúng owner trong PostgreSQL.

## Hợp đồng API/UI

- Chat nhận `conversation_id` tùy chọn; thiếu ID thì server mở phiên khi đã có consent. `history` cũ chỉ giữ tương thích validation và bị bỏ qua.
- Chat trả `conversation_id`, `memory_status`, `memory_proposals`, `user_message_id` khi lưu thành công.
- `POST /me/conversations`, `GET/DELETE /me/conversations/{id}`: chỉ owner; 404 với ID của người khác.
- `GET/POST /me/memory/facts`, `POST /me/memory/facts/{id}/confirm`, `DELETE /me/memory/facts/{id}`.
- Tạo đề xuất thủ công phải trích đúng lời user trong message gần đây của chính phiên mình; không chấp nhận đoạn tự bịa.
- `PUT /me/memory-consent` cần acknowledgment riêng; `POST /me/memory/sync` đồng bộ confirmed-only.
- `DELETE /me/memory` tắt/xóa bản Zep, không xóa fact PostgreSQL; xóa local bằng endpoint fact.
- Task async lưu owner trước dispatch; cả worker và endpoint kết quả kiểm tra owner/hạn. Không trả nội dung exception của task cho client.
- Streamlit: tab **Tiến độ → Ghi nhớ**, xác nhận/xóa, consent Zep, đồng bộ, tắt/xóa. Đổi dev identity xóa state hội thoại/checkbox consent trên UI.
- Nút xóa hội thoại gọi server trước khi dọn UI. Không retry POST chat tự động để tránh lưu trùng lượt.

## Retention và race

Xem [hợp đồng package memory](../../backend/src/memory/README.md) cho giới hạn chính xác.
Celery Beat mới chạy purge hằng ngày; một scheduler duy nhất. Đọc luôn loại dữ liệu hết hạn ngay cả khi purge chưa chạy.
Xóa fact vô hiệu hóa ngay context; bản cloud có thể còn tồn tại trong lúc chờ sync/provider phục hồi.

Quyết định consent/sync/delete serialize bằng user-row lock PostgreSQL. Dirty marker commit trước remote writes;
revoke chờ thao tác đang chạy xong, sau đó tắt quyền trước khi xóa. Purge khóa user trước owned records,
đọc lại hạn sau khi khóa để không xóa nhầm fact vừa xác nhận. **Chưa thử cạnh tranh thật trên PostgreSQL**;
SQLite test không chứng minh hành vi khóa hay độ trễ khi tranh chấp.

Worker hạ log xuống warning; async dispatch che args/kwargs trong task event/log representation.
Broker/result backend vẫn chứa nội dung nhạy cảm để xử lý task, cần mạng nội bộ và chính sách backup/retention riêng.

## Corpus chung

Mutation API mặc định tắt (`ENABLE_CORPUS_ADMIN_API=false`). Khi bật cần trusted auth có scope `corpus:write`,
collection trong `CORPUS_STAGING_COLLECTIONS`, không phải collection/alias đang phục vụ.
Tài liệu HTTP phải có nguồn HTTP(S), `data_scope=shared_knowledge`, `privacy_review_status=approved`.
Batch được kiểm tra toàn bộ trước lần ghi đầu tiên. Guard kiểm tra metadata lồng nhau, scope mâu thuẫn,
source cá nhân, email/nhãn định danh trong mọi trường text; worker/import cũng kiểm tra dấu hiệu private.

**Không phải DLP hoàn chỉnh:** nhãn approved vẫn cần người được giao quyền rà soát thực sự;
regex có thể bỏ sót PII hoặc chặn nhầm nguồn công khai. CLI nội bộ không bắt review mới cho corpus cũ.
Không audit/reindex toàn bộ collection cũ trong đợt này; không có thay đổi alias hay ghi Qdrant thật.

## Kiểm chứng trong đợt

- Regression đã tái hiện rồi sửa: client history giả; owner phiên/task; pending fact chưa confirm;
  metadata scope xung đột/PII ngoài content; nhận nhầm “kế hoạch của tôi” thành “kế hoạch cũ”;
  composer general bỏ sót sở thích local khi Zep tắt.
- Test SQL chạy SQLite in-memory bật foreign keys, user/dữ liệu giả. Có ca retention giữ fact đã xác nhận
  khi xóa transcript, FK source thành NULL; expiry fact; sync lỗi chặn recall; revoke chặn export.
- SDK thật `zep-cloud==3.30.0` tải vào thư mục tạm, dùng `httpx.MockTransport`, khóa giả:
  serialize create/add/search/delete và 503 không retry đều đạt. **Không có request Zep Cloud thật.**
- Lệnh kiểm chứng cuối và số ca được ghi ở mục kết quả cuối bên dưới. Hai cảnh báo FastAPI `on_event` deprecated là có sẵn.
- Syntax/Compose validation chỉ chứng minh source/config hợp lệ, không thay thế runtime.

## Triển khai có kiểm soát

1. Backup PostgreSQL và xác nhận migration P1 `20260815_01_p1_personalization` đã áp dụng.
2. Kiểm tra trạng thái import/process, point count, collection/alias, manifest/log cuối trước mọi restart.
   Docker daemon hiện không chạy nên chưa thực hiện được các kiểm tra runtime này.
3. Chạy `database/migrations/20260929_02_memory.up.sql` bằng tài khoản migration trên database đích.
   Script thêm bảng/index; đánh dấu mirror Zep cũ pending để thay raw history bằng confirmed-only.
   `init.sql` chỉ dành cho database mới. Không dùng create_all để migrate database hiện hữu.
4. Build backend/worker và khởi chạy đúng một `chatbot-scheduler`; deploy frontend cùng contract mới.
   Cấu hình `CHAT_RETENTION_DAYS`, auth tin cậy, các biến Zep riêng; không đưa key vào Git/log.
5. Giữ Zep production tắt đến khi test tài khoản giả: confirm → sync → recall sau khi provider index xong → xóa/revoke.
   Xác minh trên dashboard/provider rằng deletion hoàn tất; thử outage/retry và hai user không lẫn dữ liệu.
6. Chạy HTTP smoke thật `/health`, greeting, BMI, urgent, InBody/nutrition/exercise/safety retrieval, input âm422;
   thêm ownership phiên/task, proposal/confirm/delete và retention. Đo latency, đặc biệt user lock dưới tải.

Rollback: giữ Zep tắt, quay source tương thích và backup; file `down.sql` **xóa dữ liệu memory_facts/chat_tasks**,
không tự chạy rollback phá dữ liệu. Khóa `ZEP_ID_SECRET` phải ổn định để còn tìm/xóa mirror cũ.

## Gate còn mở

- Chưa chạy migration/rollback trên PostgreSQL thật, Celery/Beat/Valkey thật, HTTP container hoặc UI visual.
- Chưa có live-cloud read-after-write/deletion/async indexing; mock SDK không chứng minh chất lượng recall.
- Auth middleware production, concurrent revoke/in-flight model response, lock wait/P95 và provider retention cần kiểm thử vận hành.
- Thu hồi consent chặn thao tác mới nhưng không thể thu hồi thông tin đã nằm trong response/LLM đang chạy trước đó.
- Không tuyên bố hoàn tất account erase/backup erase hay DLP/citation quality gate từ bộ test này.

Tham chiếu API nhà cung cấp: [Thread add messages](https://help.getzep.com/v3/sdk-reference/thread/add-messages-to-a-thread),
[Users và user graphs](https://help.getzep.com/v3/users-and-user-graphs).

## Kết quả cuối

- **111 passed**, 2 cảnh báo FastAPI có sẵn, 4,15 giây (host Python 3.13): toàn bộ unit + API fast-path + 2 test SDK offline.
- Python image backend là 3.10.12; chỉ host 3.13 có sẵn. Kiểm tra AST tương thích cú pháp 3.10 không thay thế chạy dependency/runtime trong image.
- Lệnh test (khi SDK đã cài từ requirements hoặc thêm đường dẫn SDK tạm vào `PYTHONPATH`):

```powershell
$env:PYTHONPATH=(Resolve-Path 'backend/src').Path
python -B -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py backend/tests/integration/test_zep_sdk_contract.py -q -p no:cacheprovider
```

Nếu SDK chưa cài, file SDK test chủ động skip; không tính skip là bằng chứng đạt. Lần 111 ca trên **không có skip**.
Lần sandbox đầu bị `WinError 5` ở thư mục tạm pytest; rerun có quyền truy cập temp đã đạt.
- Syntax/AST Python 3.10, ba Compose `config --quiet`, và `git diff --check`: đạt.
- Docker daemon không tồn tại pipe `docker_engine`: không restart service, không migration và không dùng key thật.
- SDK cài riêng trong thư mục tạm, không thay môi trường Python chung; thư mục tải phục vụ test đã được dọn.

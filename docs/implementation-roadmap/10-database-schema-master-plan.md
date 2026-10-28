# Kế hoạch tổng thể database và data schema — Health/InBody Agent RAG

**Phiên bản tài liệu:** 0.1 — đề xuất để rà soát và phê duyệt.

**Ngày lập:** 2026-09-29. **Mốc source đối chiếu:** `a0a69b7`, nhánh `multi-agent-rag-mvp`.

**Rà soát bổ sung:** 2026-10-16, đối chiếu lại source trong working tree hiện tại;
working tree có thay đổi chưa commit nên đây không đại diện cho một commit/release.
Kết quả source delta và giới hạn runtime được ghi tại [audit hiện trạng](12-database-current-state-audit-2026-10-11.md#cập-nhật-kiểm-chứng-source-2026-10-16).
Thiết kế, mapping, ADR, kế hoạch chuyển đổi và test matrix dưới đây vẫn là **ĐỀ XUẤT CHỜ DUYỆT**;
không có schema/migration/runtime nào được thay đổi trong lần rà soát này.

**Phạm vi lượt này:** chỉ lập kế hoạch Markdown; không sửa source, tạo/chạy migration, xóa dữ liệu, restart, commit hay push.

**Kết luận:** giữ PostgreSQL và tái cấu trúc từng phần. Sửa tính toàn vẹn, quyền sở hữu và vòng đời dữ liệu trước; chuẩn hóa hồ sơ/consent và đồng bộ Zep sau. Không dựng lại database từ đầu, không thêm bảng chỉ để “đón đầu tương lai”.

**Đọc nhanh:** mục 3 nêu vấn đề; mục 5 nêu schema đích; mục 12 là lộ trình; mục 15 là các quyết định cần duyệt. Những bảng mới trong mục 5 không phải yêu cầu tạo đồng loạt.

**Thuật ngữ:** schema là cấu trúc/ràng buộc dữ liệu; FK là khóa ngoại; migration là thay đổi schema có phiên bản; backfill là chuyển/bổ sung dữ liệu cũ theo quy tắc; outbox là bảng lưu việc cần làm để worker không mất việc; retention là chính sách giữ/xóa dữ liệu; RPO là mức mất dữ liệu tối đa chấp nhận khi sự cố; RTO là thời gian khôi phục mục tiêu.

## 1. Cách đọc và mức độ chắc chắn

- **HIỆN CÓ:** đã đối chiếu source/SQL trong repo, không đồng nghĩa đã chạy ở database thật.
- **ĐỀ XUẤT:** thiết kế đích, cần được duyệt trước khi viết migration.
- **CẦN XÁC MINH:** thiếu dữ liệu runtime, quyết định sản phẩm hoặc kết quả thử nghiệm.
- **ĐỂ SAU:** chỉ triển khai khi điều kiện kích hoạt xuất hiện.

Docker daemon không khả dụng trong lần kiểm tra gần nhất. Chưa kiểm kê schema live, row count, dữ liệu lỗi, backup hay migration ledger hiện tại. Không sử dụng số liệu runtime tháng 8 hoặc test memory trước đây để khẳng định database hiện tại đã an toàn.

Tài liệu này là thiết kế kỹ thuật, không phải xác nhận tuân thủ pháp lý hoặc nghiệm thu y khoa. Các quyết định retention, xử lý dữ liệu người chưa thành niên và nhà cung cấp ngoài phải được người có trách nhiệm rà soát riêng.

### 1.1 Tài liệu và source đã đối chiếu

| Nguồn | Dùng để xác định | Giới hạn |
|---|---|---|
| [Schema cài mới](../../database/init.sql) | Bảng, cột, FK, index, ledger | Không chứng minh schema live giống file |
| [Migration P1](../../database/migrations/20260815_01_p1_personalization.up.sql), [migration memory](../../database/migrations/20260929_02_memory.up.sql) | Đường nâng cấp hiện có | Chưa chạy lại trên PostgreSQL trong đợt kế hoạch |
| [ORM P1](../../backend/src/persistence/models.py), [ORM memory](../../backend/src/memory/models.py) | Kiểu dữ liệu và quan hệ ứng dụng | Có khác biệt với ràng buộc trong SQL |
| [Request schemas](../../backend/src/persistence/schemas.py), [personalization service](../../backend/src/persistence/personalization_service.py) | Validation, xác nhận, version và owner checks | Application validation không thay thế DB constraints |
| [Memory store](../../backend/src/memory/store.py), [sync](../../backend/src/memory/sync.py), [event context](../../backend/src/memory/context.py) | Retention, consent, Zep, hiệu lực sự kiện | Chưa kiểm chứng concurrency PostgreSQL/provider thật |
| [Báo cáo P0](../P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md), [P1](../P1_PERSONALIZATION_REPORT.md), [Day17](09-day17-memory-completion-2026-09-29.md) | Bối cảnh và giới hạn bằng chứng | Kết quả lịch sử, không phải audit hiện tại |
| [Roadmap](README.md), [P2 OCR/privacy](02-p2-ocr-privacy-and-live-web.md), [SETUP](../../SETUP.md), [backend README](../../backend/README.md), [database README](../../database/README.md) | Hợp đồng sản phẩm và vận hành | Ví dụ setup không phải lệnh được phép chạy ngay |

## 2. Mục tiêu, giả định và phạm vi không làm

### 2.1 Mục tiêu phải đạt

1. Mỗi dữ liệu cá nhân có chủ sở hữu xác định; không đọc/ghi chéo user qua API, worker hoặc liên kết giữa bảng.
2. Phân biệt dữ liệu người dùng khai, đã xác nhận, do máy trích xuất và tri thức y khoa có nguồn.
3. Biết dữ liệu được thu thập để làm gì, còn hiệu lực không, được gửi cho ai và xóa ở đâu.
4. Có một nguồn chuẩn cho mỗi loại dữ liệu; không để PostgreSQL, Zep, Qdrant trở thành ba bản sự thật cạnh tranh.
5. API hiện tại tiếp tục hoạt động trong giai đoạn chuyển đổi; dữ liệu cũ không bị gán nghĩa mới im lặng.
6. Cài mới và nâng cấp từ schema cũ cho ra cùng hợp đồng schema được kiểm thử.
7. Có đường mở rộng OCR/device/team khi cần, nhưng chi phí hiện tại vẫn phù hợp MVP.

### 2.2 Giả định làm việc — chưa phải quyết định sản phẩm

- Trước mắt: một người dùng quản lý dữ liệu của chính mình; chưa có quyền truy cập của bác sĩ, huấn luyện viên hoặc tổ chức.
- Giữ PostgreSQL major 16 theo Compose hiện tại; xác minh phiên bản live trước khi chọn DDL. Không gộp nâng major database vào đợt này.
- Zep chỉ nhận sở thích đã xác nhận và có consent riêng. Không tự mở rộng sang bệnh sử, số đo hoặc transcript.
- Không yêu cầu lưu toàn bộ chat vô hạn để “agent nhớ tốt hơn”. Lịch sử ngắn hạn và fact dài hạn có vòng đời riêng.
- Các báo cáo/citation lịch sử cần truy vết phiên bản, nhưng không được lấy lý do tái lập để giữ dữ liệu sức khỏe vô hạn sau yêu cầu xóa.

### 2.3 Không nằm trong đợt nền tảng

- Đổi PostgreSQL sang MongoDB/Neo4j hoặc đưa toàn bộ dữ liệu vào Zep.
- Microservices, sharding, partition mọi bảng, event sourcing toàn hệ thống hoặc mô hình EAV cho mọi chỉ số.
- Đổi toàn bộ tên thư mục đồng thời với migration dữ liệu.
- Xây hệ thống bệnh án, chẩn đoán/kê đơn, chuẩn tích hợp y tế hoặc multi-tenant khi chưa có yêu cầu.
- Migration Qdrant lớn, đổi embedding/model và triển khai schema cá nhân trong cùng lần release.

## 3. Những vấn đề đã thấy trong source

Ưu tiên dưới đây là rủi ro thiết kế, không phải khẳng định sự cố đã xảy ra trên dữ liệu thật.

| ID | Hiện trạng cụ thể | Rủi ro | Ưu tiên |
|---|---|---|---|
| DB-01 | `chat_sessions.user_id` là nullable, `ON DELETE SET NULL`; purge bỏ qua owner NULL | Xóa user có thể để lại transcript không được purge theo owner | Chặn public release |
| DB-02 | `uploaded_files.user_id` cũng SET NULL; metadata/path không phải nội dung file ngoài DB | Xóa row/user không tự bảo đảm xóa file/OCR/cache | Chặn mở upload thật |
| DB-03 | `users` trộn tài khoản, sức khỏe, field legacy, consent và trạng thái Zep | Nhiều nơi ghi cùng khái niệm, khó quản lý quyền và thay đổi | Cao |
| DB-04 | `consent_flags` giữ trạng thái/timestamp hiện tại, không có chuỗi event riêng | Không tái hiện đầy đủ lần cấp/thu hồi, phạm vi và phiên bản thông báo | Cao |
| DB-05 | Plan có `goal_version`, `measurement_ids` JSONB, chưa có FK cho các liên kết này | DB không tự chặn liên kết thiếu hoặc khác owner; service đang gánh trách nhiệm | Cao |
| DB-06 | Một số UNIQUE/CHECK/partial index trong migration không xuất hiện tương đương ở ORM | Test tạo schema từ ORM có thể bỏ sót lỗi mà PostgreSQL sẽ chặn | Cao |
| DB-07 | `confirmed_by_user`, `confirmed_at`, source, trạng thái và expiry chưa được ràng buộc đầy đủ ở DB | Ghi trực tiếp/worker lỗi có thể tạo dữ liệu mâu thuẫn dù HTTP validation đúng | Cao |
| DB-08 | Sync/recall Zep giữ user-row lock trong lúc gọi mạng | Provider chậm có thể chặn thao tác cùng user; chưa đo lock wait | Cao, cần benchmark |
| DB-09 | Plan snapshot, raw payload, OCR text, task result chứa bản sao dữ liệu cá nhân | Xóa bản gốc chưa chắc xóa hết bản sao | Cao |
| DB-10 | Có `documents/document_chunks`, nhưng chưa có bằng chứng pipeline hiện tại duy trì chúng như catalog chuẩn | Có bảng không đồng nghĩa citation đã có chuỗi provenance bền vững | Trung bình; cần trace importer |
| DB-11 | Fresh init ghi ledger P1 trước phần tạo bảng và chưa ghi ledger memory tương đương migration | Ledger có thể không phản ánh đúng hợp đồng cài mới/nâng cấp | Cao, cần parity test |

Không sửa các vấn đề này bằng một lần `DROP DATABASE`, một migration đổi mọi bảng, hoặc chỉ đổi tên `persistence` thành `database`.

## 4. Ranh giới các kho dữ liệu

| Kho | Nguồn chuẩn cho | Được lưu | Không được coi là |
|---|---|---|---|
| PostgreSQL | Tài khoản, profile, số đo, goal/plan, check-in, fact xác nhận, consent, trạng thái tác vụ | Dữ liệu có schema, owner, trạng thái và vòng đời | Kho vector dùng chung cho dữ liệu cá nhân |
| Qdrant | Chỉ mục truy xuất có thể tái tạo | Chunk tri thức chung đã qua admission/review, ID và corpus version | Nguồn chuẩn hồ sơ hoặc sự thật từ chat |
| Zep | Bản sao tìm lại sở thích, tùy chọn | Fact được duyệt theo policy đang hiệu lực, định danh pseudonymous | Nguồn chuẩn, nơi xác nhận đúng/sai y khoa |
| Valkey/Celery | Cache, queue, kết quả ngắn hạn | Payload tối thiểu và TTL rõ ràng | Hồ sơ lâu dài hoặc bản backup |
| File/object storage | File gốc khi OCR được mở | File riêng tư, phân quyền, thời hạn, checksum | Public corpus hoặc public URL mặc định |
| Backup/log/export | Khôi phục và vận hành được kiểm soát | Bản sao được phân loại, hạn giữ và quyền truy cập riêng | Ngoại lệ miễn xóa hoặc nơi lưu toàn bộ prompt |

HMAC user ID gửi Zep vẫn là dữ liệu có thể liên kết, không tự trở thành dữ liệu ẩn danh. Tách database schema cũng không tự tạo ra phân quyền; auth, database role và cách query phải đi cùng nhau.

## 5. Mô hình dữ liệu đích

Tên bảng dưới đây là đề xuất. Giữ nguyên tên bảng/API đang hoạt động nếu việc đổi tên không đem lại lợi ích đủ lớn.

### 5.1 Các bảng giữ và chuẩn hóa

| Bảng | Trách nhiệm đích | Khóa/quan hệ chính | Việc cần làm |
|---|---|---|---|
| `users` | Định danh và trạng thái tài khoản | UUID nội bộ; mapping auth có unique | Bỏ dần health fields khỏi nơi này sau cutover; không lấy email làm owner key |
| `inbody_measurements` | Lần đo có nguồn và xác nhận | `user_id`, ID, thời điểm đo | Cột metric có kiểu/đơn vị, constraints, revision khi sửa |
| `personalization_goals` | Mục tiêu versioned | `(user_id, version)` unique; tối đa một active/user | FK predecessor cùng owner; thống nhất trạng thái public/internal |
| `personalized_plans` | Kế hoạch có đầu vào đóng băng và trạng thái | Owner, version, goal ID | Giữ snapshot; thêm quan hệ đo đạc và provenance rõ ràng |
| `check_ins` | Theo dõi do user tự báo cáo | Owner, checked_at; plan ID tùy chọn | Không suy ra check-in thuộc plan nào chỉ từ ngày gần nhất |
| `chat_sessions` | Phiên thuộc user đã xác thực | Owner bắt buộc đối với phiên cá nhân | Loại dần `external_user_id` dư thừa; cleanup dữ liệu orphan |
| `chat_messages` | Lượt nói ngắn hạn | Session, thứ tự trong phiên | Role allowlist, expiry, idempotency; không coi assistant text là fact |
| `memory_facts` | Đề xuất và sở thích đã xác nhận | Owner, loại fact, nguồn, revision | Trạng thái, thời hạn, thay thế/xóa; không chứa hồ sơ bệnh tự suy |
| `chat_tasks` | Quyền sở hữu/tình trạng xử lý chat | Task ID, owner, session nếu có | Gắn request idempotency và hết hạn; không nhân đôi raw answer trong SQL |
| `uploaded_files` | Metadata quản lý file riêng tư | Owner, storage key, expiry | Chưa mở upload khi chưa có lifecycle file thực tế |
| `documents`, `document_chunks` | Catalog tri thức chung khi pipeline đã nối | Document/revision/chunk, stable ID | Không tự nhận đây là nguồn chuẩn trước khi kiểm chứng importer |
| `schema_migrations` | Lịch sử áp dụng schema | Version; đề xuất thêm checksum/trạng thái thực thi | Ghi thành công sau khi bước tương ứng thành công; cấm sửa migration đã phát hành |

### 5.2 Bảng bổ sung có lý do cụ thể

| Bảng đề xuất | Lý do tồn tại | Các trường chính ở mức logical | Thời điểm |
|---|---|---|---|
| `health_profiles` | Tách dữ liệu sức khỏe khỏi tài khoản | `user_id` PK/FK, profile fields, `revision`, confirmation/source metadata | Đợt chuẩn hóa |
| `consent_events` | Ghi từng quyết định, không ghi đè lịch sử | ID, owner, purpose, decision, notice version, actor type, thời điểm, request ID | Đợt chuẩn hóa |
| `user_consent_state` | Đọc quyền hiện tại nhanh, có revision chống stale | PK `(user_id, purpose)`, granted, revision, last event ID | Cùng transaction với consent event |
| `plan_measurements` | Tham chiếu số đo có tính toàn vẹn | Owner, plan ID, measurement ID, revision lúc dùng | Đợt chuẩn hóa |
| `memory_sync_state` | Tách trạng thái nhà cung cấp khỏi consent | PK `(user_id, provider)`, desired/applied version, epoch, trạng thái, timestamps, error code | Đợt đồng bộ |
| `outbox_jobs` | Không mất ý định sync/delete khi worker/process chết | ID, owner/opaque cleanup handle, operation, target version, dedup key, attempts, next attempt, lease, status | Đợt đồng bộ |
| `privacy_requests` | Theo dõi export/delete xuyên nhiều kho | ID, owner hoặc tombstone handle, request type, scope, status, component receipts, expiry | Trước public release |

Không tạo bảng `memory_events` chỉ để sao chép plan/check-in: hiện lấy event context từ các bảng nghiệp vụ đã có. Chỉ thêm bảng sự kiện riêng khi xuất hiện loại sự kiện không thuộc các bảng đó.

### 5.3 Quan hệ cần bảo vệ

| Quan hệ | Cardinality | Bất biến |
|---|---|---|
| User — health profile | 1 — 0..1 | Chưa có profile không đồng nghĩa các giá trị sức khỏe bằng mặc định |
| User — measurement/goal/plan/check-in/fact | 1 — nhiều | Mọi record riêng tư có owner hợp lệ |
| Session — message | 1 — nhiều | Không có message mồ côi, thứ tự xác định |
| Plan — goal | nhiều — 0..1 | Cùng owner; goal cũ vẫn có thể được tham chiếu cho lịch sử |
| Plan — measurement | nhiều — nhiều | Qua bảng nối cùng owner; snapshot lưu revision lúc dùng |
| Check-in — plan | nhiều — 0..1 | Chỉ liên kết khi có bằng chứng/user chọn; cùng owner |
| Fact — source message | nhiều — 0..1 | Cùng owner; message có thể hết hạn trong khi fact xác nhận còn hiệu lực |
| Consent state — event | một state — một last event | Revision/state/event cập nhật nguyên tử |

FK tới ID đơn lẻ chỉ bảo đảm record tồn tại, không bảo đảm cùng người dùng. DDL chi tiết cần dùng composite FK/unique phù hợp hoặc một invariant DB tương đương đã kiểm thử, bên cạnh owner filter ở service.

### 5.4 Decision records (ADR) cần duyệt

Các quyết định dưới đây là ADR đề xuất, không phải quyết định đã được product/privacy/security owner phê duyệt.

| ADR | Chọn | Phương án không chọn | Lý do, trade-off và điều kiện rà soát |
|---|---|---|---|
| ADR-01 — PostgreSQL là nguồn chuẩn cá nhân | Giữ PostgreSQL cho account, hồ sơ, số đo, goal/plan, chat/fact và consent; chuẩn hóa additive theo miền | Rebuild database hoặc chuyển toàn bộ sang document/graph DB | Tận dụng contract owner/transaction hiện có, giảm cutover rủi ro. Đổi lại cần xử lý legacy schema và migration parity. Rà soát lại nếu có bằng chứng tải/quan hệ mới vượt khả năng PostgreSQL. |
| ADR-02 — Tách public RAG khỏi dữ liệu cá nhân | Qdrant chỉ index corpus chung đã admission/review; dữ liệu cá nhân ở PostgreSQL theo owner | Đưa OCR/profile/chat vào chung Qdrant collection | Tránh cross-user retrieval/citation và giữ quyền xóa; đổi lại không có semantic retrieval trên hồ sơ cá nhân. Chỉ mở nếu có namespace, auth filter, deletion và benchmark riêng được duyệt. |
| ADR-03 — OCR là draft tạm, không lưu tự động | UI giữ draft phiên làm việc; measurement chính thức tạo sau xác nhận | Tự lưu file, raw extraction/confidence vào `uploaded_files` | Giảm bản sao dữ liệu nhạy cảm, nhưng không thể tái dựng lỗi OCR sau phiên. Nếu cần audit parser, phải chốt retention/storage/owner trước khi bật upload. |
| ADR-04 — Consent state có lịch sử và sync bền vững | Đích có consent event/state và outbox/sync state theo đợt | Tiếp tục mở rộng JSON flags hoặc gọi provider trực tiếp trong request như hợp đồng lâu dài | JSON hiện tại đơn giản nhưng không đủ lịch sử/retry/delete receipt; outbox thêm vận hành worker và xử lý race. Chỉ triển khai sau khi thử revoke/timeout/write-muộn với provider lab. |
| ADR-05 — Hoãn SQL corpus catalog | Trước mắt coi manifest + Qdrant là đường ingest hiện hành; SQL `documents/document_chunks` chưa là nguồn chuẩn đã chứng minh | Đồng bộ thêm SQL catalog ngay trong migration cá nhân | Tránh dual-write không có reconciliation; đổi lại metadata catalog không truy vấn tập trung ở PostgreSQL. Kích hoạt khi có nhu cầu quản trị version/license/review và pipeline transactional/reconcile. |

Mỗi ADR trước DDL cần ghi người duyệt, ngày, phạm vi áp dụng, source/runtime evidence mới và quyết định thay thế nếu bị bác.

## 6. Hợp đồng dữ liệu theo từng miền

### 6.1 Tài khoản và hồ sơ sức khỏe

- `users.id` là khóa nội bộ ổn định. Auth subject phải lấy từ identity đã xác minh; nếu có nhiều issuer, unique theo `(issuer, subject)`, không theo subject toàn cầu.
- Chỉ tạo `user_identities` riêng khi hỗ trợ liên kết nhiều tài khoản đăng nhập; không đoán ghép tài khoản từ email trùng nhau.
- `health_profiles` có `revision` để tránh hai tab ghi đè âm thầm. Update kèm revision cũ; stale update trả conflict.
- `sex` và `sex_at_birth` không tự động đồng nghĩa. `full_name` và `display_name` cũng không nhất thiết thay thế nhau. Mọi mapping cần quy tắc và danh sách conflict.
- Không đổi `birth_year` thành ngày sinh 01/01 hoặc tự suy nhóm tuổi đã xác nhận. Giữ provenance legacy hoặc yêu cầu user xác nhận lại.
- Profile `goal` chỉ là dữ liệu legacy/tóm tắt; active goal chuẩn nằm ở bảng goal. Không duy trì hai nơi cập nhật độc lập.
- Sở thích từ profile và `memory_facts` không được cạnh tranh: dữ liệu có cấu trúc được user xác nhận trong profile ưu tiên; fact trái với profile phải được xem lại, không tự ghi đè.
- Tách cột không tự giải quyết consent. Mọi đường đọc context vẫn kiểm tra purpose, account status và dữ liệu còn hiệu lực.

### 6.2 Số đo, sửa dữ liệu và nguồn gốc

- Giữ các metric cốt lõi ở cột có kiểu; không chuyển toàn bộ sang `{name, value}` generic. Tên cột thể hiện đơn vị như `_kg`, `_cm`, `_percent`.
- Phân biệt `measured_at` và `created_at`; dùng timezone-aware time. Nếu nguồn chỉ có ngày, lưu độ chính xác ngày và provenance chuyển đổi, không bịa thời điểm đo.
- Confidence OCR là độ tin cậy trích xuất, không phải xác nhận của user hoặc xác suất đúng y khoa.
- Bổ sung ràng buộc cho số đo tồn tại tối thiểu một metric; confidence trong `[0,1]`; trạng thái xác nhận tương thích `confirmed_at`; source type có allowlist.
- Các khoảng metric phải thống nhất API/DB và được rà soát theo phạm vi người dùng/thiết bị. Không coi giới hạn kỹ thuật hiện tại là ngưỡng chẩn đoán; không ép dữ liệu legacy sai range thành số hợp lệ.
- Sửa metric/source của record đã xác nhận phải tăng revision và xác nhận lại thay đổi theo contract. Plan snapshot cũ không bị sửa theo số đo mới.
- Đợt đầu dùng revision + snapshot tối thiểu; chỉ thêm bảng lịch sử revision chi tiết khi cần audit sửa số đo và đã chốt retention. Không lưu mọi phiên bản raw payload vô hạn.
- Tương lai device import có khóa chống nhập trùng theo owner/provider/source event ID; không dedup chỉ bằng cân nặng/ngày đo.

### 6.3 Goal, plan, check-in và citation

- Giữ unique `(user_id, version)` và partial unique “tối đa một active/user” cho goal/plan. Test hai transaction cùng tạo version mới.
- Thêm `goal_id` cùng owner vào plan; `goal_version` lịch sử có thể giữ như snapshot, không dùng thay FK.
- Backfill plan-measurement chỉ khi ID/owner xác định. Thiếu/khác owner thì cách ly và báo cáo, không âm thầm bỏ phần tử JSON.
- Không bỏ `input_snapshot`: FK đến record hiện tại không tái hiện giá trị đã dùng lúc lập kế hoạch.
- Snapshot có `schema_version`, `captured_at`, source IDs/revisions, tối thiểu trường thực sự cần. Đây vẫn là dữ liệu sức khỏe, phải nằm trong export/delete.
- Kế hoạch “active” không tự chứng minh còn phù hợp. Khi goal đổi, số đo bị sửa/xóa hoặc safety thay đổi, đánh dấu cần xem lại; không tự áp dụng kế hoạch cũ vào hiện tại.
- Plan citation cần stable document/chunk ID, corpus version, source locator và content hash khi có. Số `[1]` trong một câu trả lời không phải ID tài liệu toàn cục.
- Chỉ có citation ID tồn tại vẫn chưa chứng minh claim được hỗ trợ. Giữ claim-level checker và clinical review gate độc lập với schema.
- Check-in giữ nhãn tự báo cáo; không tự tạo diagnosis hoặc suy ra hiệu quả điều trị.

### 6.4 Hội thoại và memory fact

- Session cá nhân mới luôn có owner; message gắn session của owner. Không cho client đưa `history` vào như lịch sử đáng tin cậy.
- Dùng thứ tự message ổn định: đề xuất `sequence_no` unique/session hoặc turn ID + vị trí. UUID ngẫu nhiên và timestamp trùng nhau không đủ mô tả thứ tự hai request đồng thời.
- Tạo một logical chat turn có idempotency key theo owner/session. Retry cùng key không tạo hai cặp message; cùng key nhưng payload khác phải conflict.
- `memory_facts`: tối thiểu `kind`, `status`, `source_type`, `source_message_id`, `confirmed_at`, `expires_at`, `revision`; thay đổi text sau confirm phải tạo xác nhận/revision mới.
- State đề xuất: pending → confirmed hoặc rejected; confirmed → superseded/revoked. Expiry được xét từ thời gian, không đợi job đổi status mới ngừng sử dụng.
- Xóa transcript không tự xóa fact đã xác nhận riêng; UI phải nói rõ điều này. Sau khi nguồn bị purge, chỉ giữ provenance tối thiểu của fact, không cất lại cả transcript ở metadata.
- Nếu dùng composite FK bảo vệ owner của source message, cần thiết kế hành vi xóa chỉ làm mất source reference, không làm NULL owner của fact. Kiểm thử SQL cụ thể trước khi chọn DDL.
- Không giữ fact mới chỉ vì Zep rút ra được. Zep không tự ghi profile/measurement, không tạo citation y khoa.

### 6.5 Consent và thông tin vận hành

- Purpose tách biệt: xử lý/lưu dữ liệu sức khỏe, cá nhân hóa, xử lý ở Zep; mục đích mở rộng phải có thông báo và quyết định riêng.
- Event consent chỉ chứa quyết định và bằng chứng tối thiểu: purpose, notice version, actor, thời điểm, request ID. Không sao chép hồ sơ sức khỏe vào audit.
- Event được bảo vệ khỏi update/delete bởi application role; không gọi là “bất biến tuyệt đối” trước database admin hoặc khi chưa có cơ chế tamper evidence.
- Consent event và current state cập nhật trong cùng transaction; current state là projection, không phải lịch sử thứ hai tự sửa độc lập.
- Không suy consent quá khứ khi backfill. Có cờ/timestamp cũ thì ghi sự kiện `legacy_imported` với mức bằng chứng thực có; thiếu phiên bản thông báo phải để unknown, không bịa.
- Thu hồi consent ngừng sử dụng mới, không tự đồng nghĩa đã xóa vật lý. Quyền yêu cầu xem/xóa dữ liệu của chính mình không phụ thuộc việc phải bật lại consent cá nhân hóa.
- Retention audit/consent cũng cần mục đích, thời hạn và quyền truy cập; không lấy chữ “audit” làm lý do giữ dữ liệu nhận diện vô hạn.

## 7. Đồng bộ Zep: thiết kế trạng thái và lỗi

### 7.1 Mục tiêu và contract

PostgreSQL ghi thay đổi fact/consent và một outbox job trong cùng transaction. Job chỉ mang ID/version/operation cần thiết; worker lấy lại dữ liệu còn được phép xử lý khi chạy. Không nhét bản sao hồ sơ vào queue/outbox để tránh phải thu hồi nhiều bản.

`memory_sync_state` phân biệt ít nhất: disabled, pending, syncing, ready, retry_pending, deletion_pending, deleted. `desired_version` khác `applied_version` nghĩa là bản cloud chưa theo kịp. “Provider đã nhận request” và “đã index để recall được” là hai sự kiện khác nhau.

Read path vẫn sử dụng local confirmed facts khi Zep tắt/lỗi/chưa sẵn sàng. Kết quả từ Zep chỉ chọn fact ID còn tồn tại, cùng owner, còn hạn, đúng quyền hiện tại; provider text không thay thế dữ liệu PostgreSQL.

### 7.2 Quy trình worker đề xuất

1. Claim job bằng lease hữu hạn; chỉ một thao tác mutating cùng user/provider được thực hiện tại một thời điểm.
2. Đọc consent revision/epoch và target version; bỏ job cũ hoặc không còn được phép, nhưng không bỏ deletion job chỉ vì consent đã thu hồi.
3. Gọi provider với deadline và retry hữu hạn cho lỗi tạm thời; không giữ user-row transaction dài suốt cuộc gọi mạng trong thiết kế đích.
4. Ghi receipt và kết quả bằng conditional update theo epoch/version; worker cũ không được đánh dấu mirror mới là ready.
5. Lease hết hạn/crash sau provider success nhưng trước DB commit phải retry/reconcile an toàn. Không giả định exactly-once delivery.
6. Khi hết retry, chuyển trạng thái cần operator xử lý và cảnh báo bằng mã lỗi/count; không log nội dung sức khỏe.

**Điểm khó phải chứng minh trước thay source hiện tại:** epoch/CAS ở PostgreSQL không ngăn được một request đã bay tới provider tiếp tục ghi. Revoke phải serialize với thao tác đang chạy, chặn re-enable khi chưa xử lý hết và bảo đảm delete chạy sau write cũ. Nếu timeout khiến kết quả remote không rõ, giữ `deletion_pending` và reconcile; không báo đã xóa.

Không thay lock hiện tại bằng một worker bất đồng bộ đơn giản rồi tuyên bố race đã hết. Cần test có điều khiển các thời điểm write/revoke/timeout/crash, kể cả provider hoàn thành muộn.

### 7.3 Thu hồi và xóa account

- Revoke transaction tăng epoch, tắt export/recall, tạo durable deletion job.
- API có thể báo đã tắt sử dụng ngay, nhưng phải báo xóa provider còn pending cho tới khi có bằng chứng theo API nhà cung cấp.
- Không hard-delete user trước khi giữ đủ cleanup handle tối thiểu để xóa Zep/file/task cache. Job không được cascade mất cùng user khi chưa hoàn tất việc ngoài DB.
- Sau cleanup, xóa/giảm định danh của receipt và handle theo policy. Khi provider ngừng hoạt động, trạng thái phải là pending/failed có chủ đích, không complete giả.
- Xoay HMAC secret cần key version/mapping hoặc kế hoạch xóa old namespace; mất secret cũ có thể làm mất khả năng tìm/xóa mirror cũ.

Zep mô tả quản lý user graph và xóa dữ liệu qua lifecycle user trong [tài liệu Users and User Graphs](https://help.getzep.com/v3/users-and-user-graphs). Vẫn phải kiểm chứng API, indexing và deletion của account/provider thật bằng dữ liệu giả trước rollout; không suy ra chính sách backup của provider từ HTTP success.

## 8. Retention, export và xóa dữ liệu

Các mốc hiện có là cấu hình source, không phải kết luận rằng phù hợp pháp lý. Mọi thời hạn mới dưới đây cần quyết định sản phẩm trước public release.

| Nhóm | Hiện có/đề xuất | Khi hết hạn hoặc user yêu cầu xóa | Cần xác minh |
|---|---|---|---|
| Transcript | Hiện mặc định 7 ngày, cấu hình 1–30; 40 message/phiên, 20 phiên/user | Không đưa vào context ngay khi hết hạn; purge vật lý theo batch | Scheduler chết, orphan session, metadata/title chứa PII |
| Pending fact | Hiện 7 ngày | Không recall/export; purge | Source đã mất trước confirmation |
| Confirmed fact | Hiện 180 ngày, tối đa 20 fact còn hạn | Ngừng local recall; tạo sync/delete cho mirror | Thời gian xóa cloud và retry |
| Chat task/result | Hiện 1 giờ | Owner endpoint không trả nữa; dọn SQL/Valkey | Queue đang chờ, retry/dead letter và result tồn đọng |
| Profile/measurement/goal/plan/check-in | Chưa có policy vật lý đầy đủ | Cần policy cho data active, soft-deleted, account closed và bản snapshot | Không mặc định “giữ mãi” |
| File gốc/OCR | Chưa mở upload API | Phải có TTL, signed access, cleanup file và text trước khi bật | Giữ metadata hay file theo mục đích nào |
| Event context | Hiện đọc plan 90 ngày, check-in 30 ngày | Ngoài cửa sổ không dùng trong context | Cửa sổ đọc KHÔNG phải retention bảng gốc |
| Consent/audit/receipt | Chưa chốt thời hạn | Giảm nhận diện, hạn quyền, purge đúng policy | Mục đích lưu và nghĩa vụ áp dụng |
| Export | Đề xuất file tải có TTL ngắn, link xác thực | Hết TTL xóa file và link; audit tối thiểu | Thời hạn cụ thể và kích thước tối đa |
| Backup/log | Chưa đủ bằng chứng vận hành | Hạn giữ riêng, mã hóa, quyền tách biệt | Restore phải áp lại yêu cầu xóa sau thời điểm backup |

### 8.1 Phạm vi xóa phải bao gồm bản sao

- Profile/measurement/plan snapshot và fact có nguồn liên quan.
- Transcript, task args/results, cache, file/OCR, export files.
- Mirror Zep, job cũ có thể tái tạo dữ liệu, audit có dữ liệu nhận diện không cần thiết.
- Backup: không cam kết xóa tức thì khỏi mọi bản backup nếu chưa có khả năng thực hiện; phải minh bạch thời hạn và quy trình restore.

Xóa một measurement trong khi plan còn snapshot có hai nghĩa khác nhau: ẩn khỏi dashboard hoặc xóa nội dung sức khỏe khỏi hệ thống. API/UI cần phân biệt và chốt policy; không dùng từ “đã xóa” chung chung cho soft delete.

### 8.2 Xử lý dữ liệu mồ côi đang tồn tại

1. Kiểm kê read-only số session/file thiếu owner, mức liên kết và phạm vi thời gian; report chỉ dùng ID/count đã giảm nhận diện.
2. Chỉ backfill owner khi mapping có căn cứ và duy nhất; không đoán từ email, tên người hoặc nội dung chat.
3. Dữ liệu chưa xác định owner không được đưa vào context/export của bất kỳ user nào.
4. Đề xuất xử lý riêng: mapping có chứng cứ, cách ly có thời hạn, hoặc purge được phê duyệt. Không tự xóa hàng loạt trong migration schema.
5. Sau xử lý, thiết lập owner bắt buộc cho dữ liệu cá nhân mới; account deletion có coordinator, không để SET NULL tạo thêm orphan.

## 9. Schema tri thức chung và mở rộng tương lai

### 9.1 Catalog tri thức — phát triển sau nền tảng cá nhân

Giữ tách biệt hoàn toàn public knowledge và personal data. Trước khi bổ sung catalog phải trace đường importer → chunk → Qdrant → BM25 → composer → citation, xác định ID nào hiện là ổn định.

Catalog đích cần biểu diễn: logical document ID, revision/content hash, nguồn/publisher/license nếu biết, trạng thái review, corpus version, chunk index/locator, embedding configuration và collection đích. “Không biết” phải được lưu như không biết; không tự tạo provenance từ tên file.

- Ưu tiên tận dụng `documents/document_chunks`; chỉ thêm `document_versions`, `corpus_versions`, `import_runs` khi đã chốt pipeline ghi chúng và nhu cầu lịch sử.
- Không ràng buộc Qdrant point ID unique toàn lịch sử nếu một chunk có nhiều embedding/collection version; xác định khóa bằng namespace đầy đủ.
- Tài liệu y khoa bị rút lại phải chặn retrieval mới; lịch sử citation vẫn hiển thị trạng thái nguồn đã rút, không coi nguồn lịch sử là còn hợp lệ.
- Corpus catalog version và Qdrant/BM25 version phải tương ứng; registry không được báo ready trước khi kiểm tra count/hash/sample retrieval theo manifest.
- Schema cá nhân có thể hoàn tất mà chưa migrate corpus. Khi làm corpus, dùng collection version mới/blue-green riêng, không sửa collection đang phục vụ.

### 9.2 Các hướng tương lai và điều kiện kích hoạt

| Nhu cầu | Khi nào mới mở | Thiết kế bổ sung | Không làm trước |
|---|---|---|---|
| OCR ảnh/PDF | Có mẫu file, policy retention, UI confirmation và kiểm thử parser | File owner, extraction run/parser version, field confidence/provenance, confirmed measurement | Tự đưa OCR thành số đo chuẩn |
| Thiết bị/wearable | Có provider và hợp đồng dữ liệu cụ thể | External measurement ID, observed time/unit/device, ingestion dedup | Một bảng metric generic không giới hạn |
| Huấn luyện viên/phòng khám | Sản phẩm xác định role và phạm vi chia sẻ | Organization/membership và access grant riêng có scope/expiry/revoke | Thêm `tenant_id` mọi bảng rồi cho rằng đã cô lập được dữ liệu |
| Liên kết đăng nhập | Có từ hai issuer/account identity cần liên kết | `user_identities`, quy trình xác minh liên kết | Gộp account cùng email |
| Memory lâm sàng | Có hợp đồng xác nhận, chuyên môn, privacy và evaluation riêng | Entity có thời gian/nguồn/phạm vi, không chỉ text fact | Nới loại fact để LLM tự suy bệnh |
| Nhiều worker/user hơn | Có profile tải, slow-query/lock/storage evidence | Index theo query, batching/partition/read replica khi có số đo | Shard hoặc đổi database theo cảm tính |
| Analytics/nghiên cứu | Có mục đích/consent và quy trình giảm nhận diện | Read model hoặc warehouse riêng, lineage và deletion propagation | Query raw health vào dashboard quản trị mặc định |
| Đổi nhà cung cấp memory | Có adapter contract và test export/delete | Provider namespace/key version, cleanup rồi chuyển mirror | Coi knowledge graph provider là dữ liệu không thể di chuyển |

## 10. Quy tắc kỹ thuật chung

### 10.1 Kiểu, constraint, index và JSONB

- UUID hiện có được giữ; không đổi toàn bộ ID sang kiểu khác trong cùng migration.
- `TIMESTAMPTZ` cho thời điểm; date cho ngày thực sự không có giờ. NULL là chưa biết, không phải 0, false hoặc giá trị trung bình.
- FK, NOT NULL, UNIQUE, CHECK dùng để bảo vệ bất biến cấu trúc. Không đặt điều kiện dựa vào thời gian chạy như “expires_at > now()” thành constraint để kỳ vọng nó tự cập nhật khi thời gian trôi.
- Partial unique cho một active record; composite FK cho liên kết cùng owner. Các range/source/state phải thống nhất SQL, ORM và API. Đây là cơ chế được PostgreSQL hỗ trợ, xem [PostgreSQL 16 — Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html).
- JSONB dùng cho snapshot/content/metadata có giới hạn kích thước và `schema_version`; không thay FK cho liên kết cần toàn vẹn. Không lập GIN index mọi JSONB khi chưa có query cần nó.
- Bắt đầu từ query thực tế: measurement `(user_id, measured_at, id)`, message theo session/thứ tự, fact theo owner/status/expiry, outbox theo status/next attempt. Đo execution plan rồi mới thêm index.
- Index retention toàn cục cần đo theo cách purge thực sự quét; index bắt đầu bằng `user_id` không tự tối ưu mọi câu quét expiry toàn bảng.

### 10.2 Giao dịch, concurrency và idempotency

- Trước khi tạo version mới: lock/unique bảo vệ phiên bản và active state; xử lý conflict thành mã lỗi có chủ đích, không trả raw SQL exception.
- Định nghĩa lock order thống nhất, transaction ngắn, timeout hữu hạn. Retry transaction lỗi serialization/deadlock chỉ khi thao tác an toàn để lặp lại.
- Idempotency scope gồm owner + loại thao tác + request key; payload hash phục vụ so sánh không được log như một kênh rò dữ liệu. Không dedup giữa user.
- Chỉ persist dữ liệu health khi đã có quyền phù hợp; urgent safety vẫn trả trước DB/LLM/RAG/web.
- Không giữ state bền vững trong RAM Uvicorn/Celery. Worker phải recheck account status, consent epoch và ownership lúc thực thi, không chỉ lúc enqueue.

### 10.3 Auth, quyền database và RLS

- Production cần auth middleware thật; schema tốt không thay thế xác minh identity. Dev header không phải production auth.
- Tách role migration, application, read-only audit/backup. Runtime app không dùng superuser; không cho client chạy SQL tùy ý.
- Giữ filter owner ở service. Đánh giá RLS như lớp bổ sung trước public release, không bật vội mà không kiểm thử connection pooling và worker context.
- Nếu chọn RLS: missing identity phải fail closed; identity context đặt theo transaction và không rò giữa request; test cả role owner/BYPASSRLS. PostgreSQL nêu rõ những role có thể bypass policy trong [PostgreSQL 16 — Row Security](https://www.postgresql.org/docs/16/ddl-rowsecurity.html).
- Tránh SQL parameter/body logging với health data. Audit chỉ lưu operation/outcome/resource handle cần thiết, không raw prompt/measurement/secret.

## 11. Chiến lược migration không phá dữ liệu

### 11.1 Một hợp đồng schema, không ba bản tự trôi

Đề xuất giữ SQL versioned migration hiện có trong đợt này; không đồng thời chuyển migration framework. Thêm runner/checksum/lock và CI parity cần thiết. Nếu sau này chọn Alembic, phải có baseline và kế hoạch chuyển ledger riêng.

- Migration là lịch sử có thứ tự; không sửa nội dung migration đã áp dụng để “khớp source mới”.
- ORM phản ánh schema đã duyệt; `create_all()` không dùng nâng cấp DB live.
- `init.sql` là baseline cài mới có parity test hoặc được sinh từ lịch sử đã xác định. Fresh install phải ghi ledger đúng các version thực sự có trong baseline.
- `CREATE TABLE IF NOT EXISTS` không chứng minh cấu trúc bảng đã đúng, cũng không thay đổi column/constraint đang sai.
- Migration runner chỉ một instance được áp dụng tại một thời điểm; mismatch checksum/unknown version phải dừng.

### 11.2 Thứ tự expand → backfill → chuyển đọc/ghi → contract

1. **Expand:** thêm bảng/cột/index cần thiết mà source cũ còn chạy được; chưa bỏ legacy fields.
2. **Backfill:** batch theo khóa ổn định, checkpoint/resume, số dòng trước/sau và báo cáo conflict; không auto-confirm dữ liệu cũ.
3. **Kiểm đối chiếu:** so sánh ID/owner/NULL/status/provenance, không chỉ so tổng row count. Xác minh FK/constraint sau khi xử lý dữ liệu lỗi.
4. **Chuyển đường đọc/ghi:** xác định rõ một nguồn chuẩn; nếu dual-write trong cùng PostgreSQL thì cùng transaction và có reconciliation. Không cho UI/service cũ mới ghi tùy ý hai nơi.
5. **Quan sát:** schema và code version tương thích, worker cũ đã drain, các đường legacy không còn ghi; khoảng quan sát do release owner duyệt.
6. **Contract:** chỉ bỏ field/bảng legacy khi không còn consumer, backup/rollback đã diễn tập và có phê duyệt riêng.

### 11.3 Mapping dữ liệu cũ cần duyệt

| Nguồn hiện tại | Đích đề xuất | Cách mapping / điều kiện |
|---|---|---|
| `users.id` | `users.id` | Giữ UUID ổn định; không tái sinh ID. |
| `users.external_id` | `user_identities(subject, issuer)` hoặc mapping auth tương đương | Giá trị hiện không ghi rõ issuer; chỉ map subject nếu nguồn xác thực xác nhận issuer và subject. Không ghép bằng email. |
| `users.full_name`, `display_name`, `email` | `users` và/hoặc `health_profiles.display_name` | Giữ khác nghĩa; email không làm khóa owner. Không tự ghi profile chưa xác nhận. |
| `users.birth_year`, `birth_date`, `age_range`, `sex`, `sex_at_birth`, `height_cm`, `activity_level`, `dietary_preferences`, `exercise_constraints`, `medical_conditions*`, `goal` | `health_profiles` có revision/provenance; goal legacy tạm qua compatibility view | Copy trường có nghĩa tương ứng; không suy ngày sinh/ngày đầu năm hoặc chuyển goal tự do thành active goal. Lập conflict report khi trường nguồn cùng nói về một khái niệm. |
| `users.consent_flags` và các timestamp sync/revoke/deletion bên trong JSONB | `consent_events` + `user_consent_state`; riêng sync sang `memory_sync_state`/outbox | Import tối đa trạng thái hiện có với nguồn `legacy/unknown`; không bịa notice version, actor hoặc lịch sử. `external_memory_sync_pending` không được map thành `ready`. |
| Toàn bộ metric/time/source/confidence/confirmed/deleted fields trong `inbody_measurements` | `inbody_measurements` + provenance/revision khi sửa | Giữ ID, owner, đơn vị, timestamp, trạng thái và soft-delete. Chỉ confirmed hợp lệ đi vào progress. Thiếu `confirmed_at`/source hoặc range bất thường -> quarantine/review, không tự xác nhận. OCR raw/page/parser không có trong nguồn hiện lưu nên không tạo dữ liệu giả. |
| `personalization_goals` (`user_id`, `version`, status, target fields, `supersedes_goal_id`) | `personalization_goals` chuẩn hóa | Giữ ID/version; map predecessor chỉ khi cùng owner; kiểm tra active uniqueness. Không diễn giải chuỗi legacy từ `users.goal` thành version lịch sử. |
| `personalized_plans.goal_version`, `measurement_ids` JSONB, input snapshot/evidence/citations/safety/status | `personalized_plans` + `goal_id` + `plan_measurements` | Map goal khi khớp duy nhất `(user_id, version)`; parse IDs và xác thực tồn tại/cùng owner. Giữ snapshot như lịch sử, gắn cờ bản sao cần policy xóa; conflict không được lặng lẽ bỏ. |
| `check_ins` fields | `check_ins`; liên kết optional tới plan sau khi có nguồn xác định | Giữ thời điểm, adherence/symptom/safety; không suy plan liên quan từ nội dung tự do. |
| `chat_sessions.user_id`, `external_user_id`, `bot_id`, timestamps | `chat_sessions` với owner bắt buộc | Session NULL owner phải cách ly; chỉ backfill bằng mapping chắc chắn. `external_user_id` chỉ bỏ sau khi mọi consumer legacy ngừng đọc/ghi. |
| `chat_messages.session_id`, role/content/timestamps | `chat_messages` theo session owner | Giữ ID/thứ tự; xóa theo retention được duyệt. Không chuyển transcript thành fact tự động. |
| `memory_facts.user_id`, `source_message_id`, status/confirmed/expiry | `memory_facts` + liên kết composite cùng owner | Giữ fact confirmed hợp lệ; pending/rejected/hết hạn theo policy. Nếu source message đã mất, giữ nguồn nullable hoặc quarantine theo quyết định; không gán owner khác. |
| `chat_tasks` SQL rows và Celery/Valkey task args/results | SQL owner/expiry + privacy lifecycle của broker/result backend | Không backfill payload từ kết quả task hết hạn. Chứng minh cleanup từng kho trước khi báo hoàn tất. |
| `uploaded_files` path/parsed fields | Chỉ giữ nếu OCR storage được duyệt; nếu không, không migrate sang bảng draft mới | Bảng/source hiện có không chứng minh file vật lý còn tồn tại. Trước migrate phải inventory tổng hợp, xác minh storage và owner; không khôi phục raw OCR từ log. |
| `documents` và `document_chunks.qdrant_point_id` | Catalog corpus riêng nếu ADR-05 được kích hoạt | Không coi SQL rows là đồng bộ với Qdrant. Khóa đích phải namespace theo document revision, corpus/collection và chunk; xác minh từ manifest/Qdrant trước import. |
| `schema_migrations` và init SQL | Một ledger/version graph tương đương fresh/upgrade | Fresh init ghi P1, memory migration ghi version riêng. Parity gate phải xác nhận cùng bảng/cột/constraint và version ledger trước khi cho phép migration mới. |

#### Bao phủ tên cột trong `database/init.sql`

Bảng dưới đây khóa phạm vi mapping tới mọi cột đang khai báo trong file cài mới. Mỗi nhóm cột ở cùng hàng đi theo cùng quy tắc của hàng tương ứng phía trên; cột mới/khác trong PostgreSQL live phải được thêm sau khi đọc catalog live.

| Bảng nguồn | Toàn bộ cột trong source DDL | Quy tắc đích áp dụng |
|---|---|---|
| `users` | `id`, `external_id`, `full_name`, `email`, `sex`, `birth_year`, `height_cm`, `activity_level`, `goal`, `medical_conditions`, `display_name`, `birth_date`, `age_range`, `sex_at_birth`, `dietary_preferences`, `exercise_constraints`, `medical_conditions_data`, `consent_flags`, `profile_confirmed_at`, `deleted_at`, `created_at`, `updated_at` | Giữ `id`; map identity theo issuer/subject đã xác minh; account fields ở `users`; health/preferences fields sang `health_profiles`; `goal` legacy read-only; consent JSON chỉ thành trạng thái legacy chưa xác minh; timestamps giữ nếu có nghĩa tương đương. |
| `inbody_measurements` | `id`, `user_id`, `measurement_date`, `height_cm`, `weight_kg`, `bmi`, `smm_kg`, `bfm_kg`, `pbf_percent`, `visceral_fat_level`, `body_water_l`, `recommendation_goal`, `source_file`, `raw_payload`, `measured_at`, `source_type`, `confidence`, `confirmed_by_user`, `confirmed_at`, `deleted_at`, `delete_reason`, `created_at`, `updated_at` | Giữ metric/owner/đơn vị/thời điểm và provenance hiện có; `raw_payload`/`source_file` cần phân loại nhạy cảm và retention; không tự nâng `legacy_unconfirmed`; không thể bổ sung OCR field gốc/parser nếu nguồn không lưu. |
| `personalization_goals` | `id`, `user_id`, `version`, `goal_type`, `target_weight_kg`, `target_date`, `training_days_per_week`, `weekly_activity_level`, `constraints`, `status`, `supersedes_goal_id`, `created_at`, `updated_at` | Giữ ID/version; map mọi FK predecessor theo cùng owner; giữ các target/constraints/status sau validation, không gộp lịch sử goal. |
| `personalized_plans` | `id`, `user_id`, `version`, `status`, `input_snapshot`, `goal_version`, `measurement_ids`, `evidence_ids`, `citations`, `safety_result`, `content`, `archived_at`, `archive_reason`, `created_at`, `updated_at` | Giữ snapshot và lifecycle; đổi `goal_version` thành `goal_id` chỉ khi match duy nhất; `measurement_ids` thành bảng nối sau owner/existence check; evidence/citation giữ namespace/version và policy xóa bản sao. |
| `check_ins` | `id`, `user_id`, `checked_at`, `adherence`, `energy_level`, `sleep_quality`, `soreness`, `symptoms`, `note`, `safety_result`, `created_at`, `updated_at` | Giữ owner/thời điểm/giá trị và safety provenance; note/symptom có retention nhạy cảm; không suy `plan_id` nếu không có link nguồn. |
| `chat_sessions` | `id`, `bot_id`, `user_id`, `external_user_id`, `title`, `created_at`, `updated_at` | Giữ ID; owner NULL phải cách ly; bỏ `external_user_id` chỉ sau khi consumer legacy dừng; kiểm tra title/metadata có PII trước retention. |
| `chat_messages` | `id`, `session_id`, `role`, `content`, `route`, `metadata`, `created_at` | Giữ session/role/thứ tự; giới hạn retention; metadata/content không được chuyển mặc định thành fact hay RAG evidence. |
| `documents` | `id`, `external_id`, `title`, `content`, `source`, `document_type`, `content_type`, `domain`, `metadata`, `created_at`, `updated_at` | Để nguyên ngoài migration cá nhân; nếu catalog được bật, giữ revision/hash/license/review status riêng và reconcile với manifest/Qdrant trước cutover. |
| `document_chunks` | `id`, `document_id`, `qdrant_point_id`, `chunk_index`, `content`, `content_type`, `token_count`, `metadata`, `created_at` | Để nguyên ngoài migration cá nhân; đích cần khóa namespaced theo document revision + corpus/collection + embedding config + chunk; không dùng unique point ID toàn lịch sử. |
| `uploaded_files` | `id`, `user_id`, `original_filename`, `storage_path`, `mime_type`, `file_size_bytes`, `processing_status`, `extracted_text`, `parsed_payload`, `created_at`, `updated_at` | Không backfill nếu chưa chứng minh row/file còn tồn tại và owner; nếu được duyệt thì owner bắt buộc, vùng lưu riêng, status draft, TTL/file cleanup receipt. |
| `memory_facts` | `id`, `user_id`, `kind`, `text`, `source_message_id`, `status`, `created_at`, `confirmed_at`, `expires_at` | Giữ status/expiry; liên kết source cùng owner; xác nhận không suy từ nội dung; đồng bộ provider chỉ là mirror có consent. |
| `chat_tasks` | `id`, `user_id`, `expires_at` | Giữ quyền tra task tối thiểu; không chứa result chuẩn; cleanup phải bao gồm Celery/Valkey. |
| `schema_migrations` | `version`, `applied_at` | Không chuyển trạng thái ledger bằng suy đoán; đối chiếu từng phiên bản live, file checksum và thứ tự migration. |

Đây là mapping đầy đủ tên cột theo **source DDL**, không phải mapping dữ liệu live. Trước backfill phải so exact columns/types/default/nullability/constraints từ PostgreSQL live với source; phát hiện cột bổ sung thì lập mapping trước khi chạm dữ liệu. Số conflict/eligible rows hiện **CHƯA BIẾT**.

### 11.4 Vận hành, dừng và rollback

- Trước restart: ghi point count Qdrant, collection/alias status, process/import job, manifest/log cuối. Không restart khi import đang chạy mà chưa quyết định rõ cách dừng/resume.
- Trước DDL/backfill: backup mã hóa, restore vào DB tạm, kiểm tra dung lượng/lock window, writer inventory và quyền migration. Không chạy trực tiếp từ ví dụ trong tài liệu cũ.
- Một số thao tác online không chạy chung transaction với toàn bộ migration; ví dụ `CREATE INDEX CONCURRENTLY` có giới hạn riêng và có thể để lại index invalid khi lỗi. Runbook phải xử lý trạng thái đó theo [PostgreSQL 16 — CREATE INDEX](https://www.postgresql.org/docs/16/sql-createindex.html).
- Dừng nếu owner mismatch mới, invariant sai, error/latency vượt ngưỡng đã chốt, checksum mismatch hoặc backup chưa restore được. Không “sửa tiếp trên production” mà thiếu điểm khôi phục.
- Ưu tiên quay application về đường cũ tương thích trong giai đoạn expand; bảng/cột thêm được giữ lại khi vô hại. `down.sql` xóa bảng mới là rollback mất dữ liệu, không dùng làm lựa chọn mặc định.
- Sau cutover đã có dữ liệu chỉ schema mới hiểu, rollback cần forward-fix hoặc quy trình replay/reconcile được thử; restore snapshot cũ có thể mất write mới. Phải chốt RPO/RTO và phê duyệt trước release.
- Restore từ backup phải áp lại deletion/consent revocation sau thời điểm snapshot trước khi mở truy cập hoặc bật lại sync Zep.

## 12. Bốn đợt triển khai và điều kiện qua đợt

Không đặt lịch theo số ngày khi chưa có row count, tải và số người thực hiện. Mỗi đợt chỉ đi tiếp khi có bằng chứng đạt gate.

### Đợt 0 — Chốt hợp đồng và audit live read-only

**Mục tiêu:** biến giả định thành quyết định, có baseline đáng tin cậy trước DDL.

**Đầu ra:** schema inventory/live version; data dictionary v1; owner/deletion matrix; query/writer inventory; legacy conflict report; retention decision; migration/backup plan và ERD chi tiết được duyệt.

**Kiểm tra:** schema live so với init/migrations/ORM; NULL/orphan/duplicate/cross-owner links; phân bố confirmed/timestamp/source; snapshot chứa PII; storage và query latency. Chỉ report tổng hợp, không commit dữ liệu sức khỏe thật.

**Qua đợt khi:** schema/data conflict được định lượng; quyết định bắt buộc ở mục 15 có owner; backup restore thử thành công; xác định rõ bản live nào sẽ nâng cấp. Chưa đủ bằng chứng thì dừng trước DDL, không suy từ SQLite test.

### Đợt 1 — Gia cố toàn vẹn và quyền sở hữu

**Mục tiêu:** xử lý DB-01/02/06/07/11 trước khi mở rộng bảng mới.

**Đầu ra:** regression tests; migration bổ sung constraints/indexes và parity; kế hoạch/công cụ xử lý orphan có kiểm soát; chuẩn confirmation/expiry; sửa retention owner NULL theo policy đã duyệt.

**Kiểm tra:** PostgreSQL thật, hai user và hai transaction; xóa user/session/source message; direct invalid INSERT/UPDATE; fresh install so với upgrade; worker retry; urgent không bị DB chặn.

**Qua đợt khi:** không tạo orphan mới; dữ liệu cũ đã xử lý hoặc cách ly có phê duyệt; DB reject liên kết sai owner và trạng thái sai trong các quan hệ được gia cố ở đợt này; parity đạt; rollback diễn tập không làm mất bản ghi ngoài phạm vi. Các liên kết plan còn lưu trong JSON được chuyển sang quan hệ có ràng buộc ở Đợt 2, không tính là đã hoàn tất ở đây.

### Đợt 2 — Chuẩn hóa hồ sơ, consent và liên kết nghiệp vụ

**Mục tiêu:** một nguồn chuẩn cho profile/goal/fact, consent có lịch sử, plan có liên kết rõ ràng.

**Đầu ra:** `health_profiles`, consent event/state, `plan_measurements`, plan-goal relation; mapping/backfill report; API adapters giữ contract; UI hiển thị xác nhận/thu hồi/xóa đúng nghĩa.

**Kiểm tra:** conflict migration; stale revision; sửa số đo đã confirm; goal mới làm plan cần review; user không cần bật lại personalization để yêu cầu xóa; consent cũ không bị nâng thành opt-in mới.

**Qua đợt khi:** backfill đầy đủ theo dữ liệu đủ điều kiện, mọi conflict có quyết định; old/new read parity đạt; không dual authority; ownership/API regression đạt; contract/drop legacy chỉ khi được duyệt riêng.

### Đợt 3 — Lifecycle đa kho và chuẩn bị mở rộng

**Mục tiêu:** export/delete/sync không mất việc, không tái tạo dữ liệu đã thu hồi.

**Đầu ra:** `memory_sync_state`, outbox, privacy requests; worker leases/idempotency/reconciliation; deletion receipts; metrics và runbook restore/recovery; feature gates cho OCR/device/catalog.

**Kiểm tra:** worker crash/duplicate delivery, revoke giữa sync, timeout nhưng provider ghi muộn, expiry, account delete, restore backup; SDK offline và cloud với dữ liệu giả; HTTP thật và tải DB dưới concurrency.

**Qua đợt khi:** không job cũ đánh dấu ready hoặc tái xuất dữ liệu đã bị thu hồi; deletion pending không báo complete; mọi kho có receipt/giới hạn rõ; source, migration, worker và HTTP runtime khớp phiên bản. Chỉ sau đó mới xem xét public release, cùng auth/safety/RAG gates của dự án.

## 13. Ma trận kiểm thử bắt buộc

| ID | Ca kiểm thử | Kết quả phải chứng minh | Môi trường |
|---|---|---|---|
| T01 | Fresh install và upgrade mọi baseline hỗ trợ | Bảng/cột/type/default/index/FK/CHECK/ledger tương đương | PostgreSQL cùng major deploy |
| T02 | Owner A tham chiếu measurement/message/goal của B | Cả API/service và DB invariant chặn | PostgreSQL + HTTP |
| T03 | Xóa session, source message, user và file | Không orphan mới; fact giữ/mất đúng policy; file ngoài DB có cleanup | DB + worker + storage giả/lab |
| T04 | Confirmed thiếu timestamp; confidence/range/state sai | DB và API reject hoặc migration quarantine rõ | DB trực tiếp + unit |
| T05 | Hai request tạo active goal/plan đồng thời | Một active/user, version không trùng, lỗi có chủ đích | Hai transaction PostgreSQL |
| T06 | Hai tab sửa profile/measurement cùng revision | Không lost update im lặng | HTTP + DB |
| T07 | Retry cùng chat/request key | Một logical turn; key reuse payload khác conflict | HTTP + Celery |
| T08 | Pending/expired/revoked/superseded fact | Không vào context/recall/export | Unit + integration |
| T09 | Xóa số đo đã nằm trong plan snapshot | Đúng chính sách xóa cả bản sao, không còn nhãn “đã xóa” sai | DB + API/UI |
| T10 | Consent grant/revoke/backfill legacy | Event và state cùng revision; không consent bịa | DB + migration |
| T11 | Worker crash sau remote success, trước commit | Retry/reconcile không nhân đôi hoặc ghi đè state mới | Fault injection + provider lab |
| T12 | Revoke/account delete giữa sync; remote hoàn thành muộn | Chặn dùng mới, delete sau write, không re-enable sớm | Concurrency + provider lab |
| T13 | Scheduler tắt, lease treo, retry hết hạn | Read vẫn loại expired; alert, retry bounded, không mất delete job | Worker/Valkey thật |
| T14 | Restore backup trước thời điểm xóa | Reapply deletion ledger trước phục vụ/sync | Restore drill riêng |
| T15 | RLS nếu được chọn, connection reuse và worker thiếu identity | Không rò identity/row; role không bypass ngoài ý muốn | PostgreSQL với role thật |
| T16 | Prompt injection trong chat/fact/OCR/document | Không thành chỉ thị; nguồn cá nhân không thành citation chung | Harness + integration |
| T17 | Urgent/BMI, DB hoặc Zep chậm/lỗi | Urgent fast-path; 0 LLM/RAG/web ở fast-path; không vô tình gọi Zep | Unit sentinel + HTTP đo thật |
| T18 | Corpus/embedding version khác và nguồn bị rút | Không trộn benchmark/citation/retrieval namespace | RAG integration riêng |

SQLite chỉ phục vụ unit nhanh. Không dùng SQLite để chứng minh PostgreSQL row lock, partial index, RLS, JSONB hoặc migration production.

### 13.1 Chỉ số và bằng chứng nghiệm thu

- Integrity: 0 liên kết khác owner; 0 orphan mới; 0 active record trùng; 0 mismatch schema chưa được duyệt.
- Migration: số record đủ điều kiện, migrated, conflicted, quarantined; checksum/ID continuity và thời gian/lock impact. Không giấu record lỗi khỏi mẫu số.
- Lifecycle: số pending delete, tuổi job lâu nhất, retry count, sync lag, orphan/file count, expired data còn đọc được bằng 0.
- Performance: baseline và sau migration trên cùng dataset/config; P50/P95 query, transaction, lock wait; concurrency 1/4/16 là kịch bản thử đề xuất, không phải dự báo tải sản phẩm.
- Giữ gate dự án: urgent/tool-only P95 dưới 500 ms và 0 LLM/RAG/web; không request chuẩn quá 60 giây. Ngưỡng riêng cho DB/sync/delete phải được chốt ở Đợt 0 trước đo nghiệm thu.
- Mỗi report ghi source commit, DB version, migration versions, fixture seed/hash, kích thước dữ liệu, môi trường, test pass/fail/skip và phần NOT_RUN. Test xanh không suy ra clinical accuracy.

## 14. Ảnh hưởng tới code và tài liệu khi triển khai sau này

| Khu vực | Thay đổi dự kiến | Ràng buộc |
|---|---|---|
| `database/init.sql`, `database/migrations/` | Canonical schema lifecycle, additive migrations, runner/parity | Không sửa migration đã áp dụng; không tự drop legacy |
| `backend/src/persistence/models.py`, `memory/models.py` | ORM khớp constraints và quan hệ đích | Không dùng create_all thay migration |
| `personalization_service.py`, `schemas.py` | Profile/revision/consent/plan mapping | Giữ `/me` contract qua adapter khi chuyển đổi |
| `memory/store.py`, `sync.py`, `chat.py` | Ownership, lifecycle, outbox và idempotency | Safety fast-path giữ nguyên; không mở rộng cloud payload |
| `api/memory.py`, `api/personalization.py`, `api/app.py` | Xóa/export/task status có nghĩa rõ | Không trả PII/log exception; owner từ auth |
| `jobs/tasks.py` | Durable cleanup, lease/retry/reconcile | Chỉ xử lý ID/permission mới nhất, không log payload |
| Frontend Streamlit | Conflict UI, consent/history, deletion pending/complete | Không bắt consent lại để user được quyền xóa |
| Tests/evals/docs | PostgreSQL integration, migration, concurrency, runbook | Tách source/mock/runtime/clinical evidence |

Tên thư mục dễ hiểu là việc riêng: có thể đề xuất `database/` cho kết nối/repository và `personalization/` cho nghiệp vụ khi tái cấu trúc source. Không cần đổi thư mục để đạt schema correctness, không gộp hai migration lớn vào nhau.

## 15. Các quyết định cần chốt trước implementation

Các vai trò dưới đây là trách nhiệm cần giao, chưa phải người đã được chỉ định.

| ID | Câu hỏi | Đề xuất ban đầu | Ai duyệt / chặn bước nào |
|---|---|---|---|
| D01 | Sản phẩm chỉ self-service hay chia sẻ cho tổ chức/coach? | Self-service trước | Product owner; trước logical schema final |
| D02 | Có hỗ trợ người dưới 18 tuổi? | Chưa mở luồng mới khi chưa có policy phù hợp; không tự xóa dữ liệu cũ | Product + privacy reviewer; trước release |
| D03 | Trường legacy xung đột lấy nguồn nào? | Không tự gộp; review mapping/conflict | Backend + data owner; trước backfill |
| D04 | Thời hạn dữ liệu sức khỏe/snapshot/soft-delete/file/audit/backup? | Giữ current memory TTL làm điểm bắt đầu, chốt riêng các nhóm thiếu | Product + privacy reviewer; trước lifecycle rollout |
| D05 | “Xóa measurement”, “quên fact”, “xóa account” có phạm vi nào? | UI/API tách rõ hide/revoke/erase; kể cả bản sao | Product + backend; trước delete endpoints |
| D06 | Thông báo consent Zep phiên bản nào, dữ liệu gì được gửi? | Confirmed preferences only, mặc định tắt | Product + privacy reviewer; trước cloud rollout |
| D07 | Auth issuer, role và RLS? | Trusted auth bắt buộc; quyết định RLS dựa trên threat model/test pooling | Security/backend; trước public release |
| D08 | RPO/RTO, backup giữ bao lâu, thời gian maintenance? | Chưa có số đo nên không cam kết thời gian | Operator + product; trước DDL live |
| D09 | DB latency, sync lag, deletion SLA và thời gian báo operator? | Đo baseline rồi chốt con số có thể vận hành | Operator + backend; trước nghiệm thu |
| D10 | PostgreSQL catalog có làm nguồn chuẩn corpus không? | Trace pipeline trước; hoãn migration corpus khỏi đợt cá nhân | RAG/data owner; trước catalog rollout |

Nếu chưa có người phụ trách privacy/operator riêng, chủ dự án phải nhận rõ trách nhiệm ra quyết định hoặc giữ tính năng tương ứng ở chế độ nội bộ/tắt. Không đánh dấu “đã duyệt” chỉ vì tài liệu có hàng checklist.

## 16. Checklist phê duyệt và Definition of Done

### Để bắt đầu viết migration

- [ ] Người dùng duyệt phạm vi tái cấu trúc từng phần, không rebuild database.
- [ ] Đợt 0 hoàn tất: live inventory, mapping conflict, owner/deletion matrix và data dictionary/ERD.
- [ ] Chốt các quyết định D01–D10 cần thiết cho đợt sắp triển khai.
- [ ] Có test tái hiện rủi ro, baseline và rollback/recovery plan cụ thể.
- [ ] Backup restore thử thành công; xác nhận import/runtime không bị gián đoạn ngoài kế hoạch.

### Để gọi một đợt đã triển khai xong

- [ ] Source, SQL, ORM, API và UI cùng hợp đồng; migration parity đạt trên PostgreSQL.
- [ ] Test unit/integration/concurrency liên quan đạt, skip/NOT_RUN được ghi rõ.
- [ ] Data reconciliation không còn lỗi chưa có quyết định; không cross-user leak.
- [ ] Deploy có kiểm soát; HTTP runtime và worker thực sự nhận đúng version.
- [ ] Đo trước/sau, thử lỗi/rollback/restore và cập nhật runbook.
- [ ] Không đưa secret/dữ liệu sức khỏe thật vào Git, log hoặc report.

### Trạng thái hiện tại

- [x] Lập kế hoạch tổng thể từ source và tài liệu hiện có; phân biệt hiện trạng, đề xuất và tương lai.
- [x] Rà soát lại source working tree ngày 2026-10-16; bổ sung ADR đề xuất, mapping field-group và liên kết tới audit bằng chứng.
- [ ] Mapping exact column/type và số lượng conflict từ PostgreSQL live — chưa thể làm vì runtime access bị chặn.
- [ ] Schema đích/retention/DDL được phê duyệt — chưa thực hiện.
- [ ] Audit PostgreSQL live, migration và load/concurrency — chưa thực hiện trong đợt này.
- [ ] Triển khai thay đổi database theo kế hoạch — chưa thực hiện.

**Bước tiếp theo được đề xuất:** cấp quyền kiểm tra PostgreSQL read-only và Docker/runtime phù hợp để hoàn thành inventory/restore evidence của Đợt 0; chốt exact mapping, conflict report và các quyết định D01–D10 cùng người duyệt. Chỉ sau đó mới viết migration Đợt 1. Không tiếp tục tự động sang sửa code/database chỉ vì tài liệu đã được tạo.

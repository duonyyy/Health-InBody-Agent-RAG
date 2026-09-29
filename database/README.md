# PostgreSQL — Health/InBody Agentic RAG

PostgreSQL là source of truth cho dữ liệu người dùng; Qdrant chỉ lưu vector và
metadata retrieval. Schema cài mới nằm ở `database/init.sql`. Database đã tồn
tại phải dùng migration, vì script trong `docker-entrypoint-initdb.d` không chạy
lại khi volume PostgreSQL đã có dữ liệu.

## Migration hiện hành

```text
database/migrations/
├── 20260815_01_p1_personalization.up.sql
└── 20260815_01_p1_personalization.down.sql
```

Migration P1 chạy trong transaction, idempotent cho thao tác `up`, ghi ledger
`schema_migrations`, và có `down` để phục hồi schema P0. `down` làm mất dữ liệu
được tạo trong các bảng P1; phải backup trước rollback production.

Ví dụ áp dụng trong môi trường local Docker:

```powershell
Get-Content -Raw ..\database\migrations\20260815_01_p1_personalization.up.sql |
  docker compose exec -T postgres-db psql -U health_user -d health_inbody -v ON_ERROR_STOP=1
```

Không đưa mật khẩu vào command hoặc commit. User/database thực tế phải lấy từ
deployment secret/configuration.

## Quan hệ P1

```text
users
├── inbody_measurements      # confirmed/unconfirmed, cursor, soft delete
├── personalization_goals   # history theo version, một active goal/user
├── personalized_plans      # input snapshot, evidence, safety, version
├── check_ins               # adherence/symptom và safety result
├── chat_sessions
│   └── chat_messages
└── uploaded_files

documents
└── document_chunks -> qdrant_point_id
```

Mọi bảng P1 có khóa ngoại `user_id` và index bắt đầu bằng `user_id`. Service
luôn resolve database user từ authenticated subject, rồi lọc đồng thời
`resource_id + user_id`; resource không thuộc owner trả 404 để không tiết lộ sự
tồn tại.

## Bảng và trường chính

### `users`

P1 bổ sung `display_name`, `birth_date` hoặc `age_range`, `sex_at_birth`,
`dietary_preferences`, `exercise_constraints`, `medical_conditions_data`,
`consent_flags`, `profile_confirmed_at` và `deleted_at`. Các trường legacy vẫn
được giữ để migration tương thích; API `/me/profile` không trả email hoặc
`external_id`.

### `inbody_measurements`

Ngoài các metric InBody, P1 có:

- `measured_at TIMESTAMPTZ` cho timeline/cursor ổn định;
- `source_type`, `confidence` và `confirmed_by_user`;
- `confirmed_at` để truy vết xác nhận;
- `deleted_at`, `delete_reason` cho soft delete.

Chỉ record `confirmed_by_user=true AND deleted_at IS NULL` được dùng cho
progress, plan snapshot và Agent personalization.

### `personalization_goals`

Mỗi thay đổi tạo version mới. Goal active trước được chuyển thành `superseded`;
unique partial index bảo đảm tối đa một active goal trên mỗi user.

### `personalized_plans`

Lưu `input_snapshot`, `goal_version`, measurement IDs đã xác nhận,
`evidence_ids`, citations, `safety_result`, structured content và trạng thái.
Active plan trước được archive khi active version mới được tạo.

### `check_ins`

Lưu check-in có thời gian, adherence, energy/sleep/soreness, symptom và kết quả
safety deterministic. Check-in không tự sửa profile, goal hoặc plan.

## Retention và recovery

- Measurement delete hiện là soft delete; dữ liệu vẫn tồn tại cho tới khi có
  retention/purge job được phê duyệt.
- User delete ở database cascade các bảng health P1. Public account-delete và
  export API thuộc privacy lifecycle tiếp theo, chưa được tuyên bố là hoàn tất.
- Backup PostgreSQL phải được mã hóa và restore-test định kỳ.
- Không log subject, raw health metric, condition hoặc payload đầy đủ.
- Qdrant backup/rollback độc lập với migration PostgreSQL; migration P1 không
  đổi alias/collection Qdrant.

## ORM

ORM tương ứng nằm tại `backend/src/persistence/models.py`; logic owner-scoped
nằm tại `backend/src/persistence/personalization_service.py`. Không dùng
`Base.metadata.create_all()` để thay thế migration trên database đã có dữ liệu.

## Bộ nhớ Day17 — source 2026-09-29

Migration `migrations/20260929_02_memory.up.sql` chạy sau P1, thêm `memory_facts`,
`chat_tasks` và index retention. Chat session/message hiện hữu vẫn dùng tiếp.
Down migration xóa hai bảng mới và dữ liệu trong chúng; cần backup trước rollback.
ORM mới ở `backend/src/memory/models.py`; chưa chạy migration này trên database thật.
Chi tiết [retention và triển khai](../docs/implementation-roadmap/09-day17-memory-completion-2026-09-29.md).

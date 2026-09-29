# P1 Personalization, Progress Tracking và User Data Safety — Báo cáo nghiệm thu

**Ngày kiểm chứng:** 2026-08-15 (Asia/Bangkok)

**Branch:** `multi-agent-rag-mvp`

**Phạm vi:** backend API, PostgreSQL migration, Agent integration, frontend auth contract và runtime HTTP.
**Kết luận:** **GO cho P1 backend/local integration; NO-GO cho public production cho tới khi nối auth middleware/IdP thật.**

## 1. Kết quả chính

P1 đã chuyển personalization từ các endpoint path-user không có ownership sang
API `/me` lấy identity từ auth dependency. Profile, goal, measurement, progress,
plan và check-in đều owner-scoped. Agent chỉ nhận dữ liệu khi user đã consent và
measurement đã được xác nhận; response chỉ trả provenance tối thiểu, không trả
raw personalization context.

| Gate | Kết quả | Bằng chứng |
|---|---:|---|
| Backend unit + integration tests | 59/59 pass | `python -m pytest tests -q -p no:cacheprovider` |
| HTTP acceptance thật | 39/39 pass | `python backend/scripts/evaluate_p1.py` |
| Cross-user measurement | Pass | B GET/PATCH/DELETE measurement A đều 404 |
| Cross-user plan | Pass | B archive plan A trả 404 |
| Unauthenticated `/me` | Pass | 401 |
| Body user borrowing | Pass | Auth A + body `user_id=B` trả 403 |
| Confirmed-only progress | Pass | Record 90 kg chưa confirm bị loại; delta 78 → 77 kg = -1.0 kg |
| Soft delete | Pass | Owner DELETE trả 204; GET sau delete trả 404 |
| Cursor/owner CRUD | Pass | Hai page không overlap; owner PATCH thành công và BMI được tính lại |
| Consent fail-closed | Pass | Revoke consent được phép; measurement write sau revoke trả 409 |
| Goal safety/history | Pass | Target cực đoan trả 409; history giữ version `[2, 1]` |
| Plan provenance | Pass | Có input snapshot, goal version 2, confirmed measurement ID, evidence và safety result |
| Plan lifecycle | Pass | current/list/archive và archived-not-current đều đúng |
| Active plan thiếu evidence | Pass | 409; citation phải map đủ evidence IDs |
| GET profile không có side effect | Pass | Empty profile trả default; PostgreSQL không tạo read-only user row |
| Symptom safety | Pass | Check-in đau ngực/khó thở được phân loại `urgent` |
| Check-in list | Pass | Owner list trả đúng record và safety result |
| Urgent Agent fast-path | Pass | Có profile vẫn `urgent_safety`, HTTP khoảng 19.82 ms, không cần LLM/RAG |
| Migration rollback rehearsal | Pass | Database tạm chạy `P0 → up → down → up` thành công |
| Qdrant không bị tác động | Pass | alias giữ nguyên; collection green, 23.608 points, update queue 0 |

Synthetic user của các HTTP acceptance run đã được xóa khỏi PostgreSQL sau khi
ghi nhận kết quả; delete cascade chỉ tác động test data có prefix `p1-eval-*`.

## 2. Ma trận yêu cầu P1

### 2.1 Profile

| API | Trạng thái | Kiểm soát |
|---|---|---|
| `GET /me/profile` | Có | Không expose email/external subject |
| `PUT /me/profile` | Có | Replace controlled fields, sanitize text/list |
| `PATCH /me/profile` | Có | Chỉ field allowlist, reject payload rỗng |

Schema hỗ trợ display name, age range hoặc birth date, sex at birth, height,
activity, goal, dietary preference, exercise/medical constraints và consent.
Không cho đồng thời `age_range` và `birth_date`; ngày sinh tương lai và height
ngoài range bị 422.

### 2.2 Goal versioning

- `GET/PUT /me/goals/current` và `GET /me/goals/history`.
- Mỗi update tạo version mới; active goal cũ chuyển `superseded`.
- Partial unique index bảo đảm tối đa một active goal/user.
- Nếu có confirmed starting weight, target thay đổi quá 1% body weight/tuần bị
  409. Nếu thiếu start weight/date, API ghi data-quality note thay vì đoán.

### 2.3 Measurement và progress

- Cursor CRUD tại `/me/measurements`; cursor ổn định theo
  `(measured_at DESC, id DESC)`.
- Validate timezone, thời gian tương lai, range metric, source/confidence và ít
  nhất một metric.
- BMI được server tính lại từ height/weight; BMI client lệch quá 0.5 bị từ chối.
- Delete là soft delete với `deleted_at/delete_reason`.
- `/me/progress/summary` và `/me/progress/timeline` chỉ dùng
  `confirmed_by_user=true AND deleted_at IS NULL`.
- Delta chỉ mô tả chênh lệch; response luôn nêu giới hạn thiết bị, hydration,
  timing và không suy ra cải thiện/nhân quả.

### 2.4 Plan và check-in

- Plan create/current/list/archive; versioned, active plan cũ được archive.
- Server tự chụp `input_snapshot` từ profile, active goal và measurement owner
  đã confirm; client không thể gắn measurement của user khác.
- Lưu `goal_version`, measurement IDs, evidence IDs, citations,
  `safety_result`, structured content và status.
- Active plan bị chặn khi safety là `medical_caution` hoặc `urgent`.
- Check-in create/list; symptom chạy deterministic medical safety. Check-in
  không tự thay profile/goal/plan.

### 2.5 Agent integration

Luồng hiện tại:

```text
authenticated subject
  -> consent check
  -> selected profile fields
  -> active goal
  -> latest confirmed, non-deleted measurement
  -> safety pre-check
  -> urgent deterministic fast-path hoặc Agent graph
```

Các mặc định ngầm `70 kg`, `fat_loss`, `moderate`, `3 buổi` và `beginner` đã bị
loại khỏi nutrition/training agent. Khi thiếu input, agent trả `need_more_info`.
LLM/embedding vẫn model-agnostic qua environment; P1 không hard-code model.

Response trả:

```json
{
  "personalization_used": {
    "available": true,
    "reason": null,
    "provenance": [
      {"type": "profile", "confirmed_at": "..."},
      {"type": "measurement", "id": "...", "confirmed_at": "..."},
      {"type": "goal", "id": "...", "version": 2}
    ]
  }
}
```

Raw profile/condition/measurement context không được echo trong Agent response.
Debug context chỉ tồn tại khi development + explicit flag và redact medical
condition thành `present/count`.

## 3. Auth và ownership

### Production contract

`AUTH_MODE=production` là mặc định. API chỉ tin identity do trusted middleware
đặt vào `request.state.current_user`. Header `X-Dev-User-Id` bị bỏ qua và request
không có server identity trả 401.

### Local development

Chỉ khi `AUTH_MODE=development`, backend mới chấp nhận `X-Dev-User-Id` sau khi
validate format. Legacy `/users/{user_id}/*` mặc định trả 404; muốn bật cần đồng
thời `ENABLE_LEGACY_USER_ENDPOINTS=true`, development mode và path user phải
khớp authenticated subject.

Frontend không còn gửi `user_id` trong chat body. `API_AUTH_MODE=development`
mới thêm dev header; production UI không hiển thị editable identity.

### Production blocker cần giải quyết trước public release

Repository chưa chứa IdP/JWT middleware cụ thể để tạo
`request.state.current_user`. Đây là secure fail-closed contract, nhưng standalone
production hiện trả 401 cho `/me` và chat. Cần tích hợp provider thật, xác minh
issuer/audience/expiry và chạy lại ownership suite. Không được “khắc phục” bằng
cách bật development header production.

## 4. Database migration

Các file:

- `database/migrations/20260815_01_p1_personalization.up.sql`
- `database/migrations/20260815_01_p1_personalization.down.sql`
- `database/init.sql` cho fresh install.

Live database trước migration: users 1, measurements 0, chat sessions/messages
0. Migration chạy transaction và ghi ledger
`20260815_01_p1_personalization`. Sau migration, row count cũ không đổi; các bảng
goal/plan/check-in ban đầu rỗng. `measured_at`, `confirmed_by_user` và
`consent_flags` có NOT NULL phù hợp.

Rollback được diễn tập trên database tạm từ schema P0 trong commit hiện tại:

1. nạp P0 `database/init.sql` từ Git;
2. chạy `up`;
3. chạy `down`;
4. chạy lại `up`;
5. xác minh ledger và ba bảng P1;
6. xóa database tạm.

`down` là schema-safe nhưng lossy đối với dữ liệu P1; production phải backup
trước rollback.

## 5. Data safety và retention

Đã có:

- consent flags fail-closed cho Agent personalization;
- owner filter trong SQL, không chỉ kiểm tra ở controller;
- confirmed/unconfirmed provenance;
- soft delete measurement;
- generic 503 khi persistence lỗi, không echo exception/secret;
- log không chứa authenticated subject hoặc raw P1 payload;
- synthetic fixture, không commit PII thật.

Chưa có và phải nằm trong privacy lifecycle tiếp theo:

- self-service account export/delete;
- retention/purge worker cho soft-deleted measurement;
- encrypted backup policy và restore drill theo lịch;
- audit event store bất biến cho consent/access/delete;
- field-level encryption nếu threat model yêu cầu.

## 6. Test và runtime evidence

### Automated tests

```text
59 passed, 0 failed, 0 skipped
```

Ba warning không làm sai gate: Starlette TestClient chuyển dần sang `httpx2` và
FastAPI `on_event` đã deprecated. Đây là maintenance debt, không phải lỗi P1.

Coverage mới bao gồm auth modes, schema boundaries, debug redaction, degraded
DB context, no-default Agent behavior, urgent fast path có personalization và
API fast-path integration.

### HTTP acceptance

Runner `backend/scripts/evaluate_p1.py` tạo hai synthetic owner qua API thật,
thực hiện 39 checks, rồi operator xác minh GET profile không tạo row và dọn đúng
hai test users. Kết quả run cuối:

- nhanh nhất: unauthenticated reject khoảng 5.77 ms;
- chậm nhất: owner measurement PATCH khoảng 38.62 ms;
- authenticated urgent chat: khoảng 10.58 ms;
- urgent Agent có profile: khoảng 21.01 ms;
- toàn bộ 39 checks pass.

Các số này là smoke latency trên máy local, không phải P50/P95 production hoặc
load benchmark.

## 7. Files chính

- `backend/src/auth/context.py` — identity boundary.
- `backend/src/api/personalization.py` — `/me` router.
- `backend/src/persistence/schemas.py` — validated request models.
- `backend/src/persistence/personalization_service.py` — owner-scoped domain service.
- `backend/src/persistence/models.py` — ORM P1.
- `backend/src/agents/graph.py` — confirmed context, provenance, no guessing.
- `backend/scripts/evaluate_p1.py` — repeatable HTTP acceptance.
- `database/migrations/` — up/down migration.

## 8. Quyết định

P1 backend đáp ứng điều kiện mục tiêu: personalization API, progress, ownership,
migration, Agent integration và report đều có implementation + runtime evidence.
Có thể chuyển sang UI/client phase hoặc P2 privacy lifecycle.

Không được gọi toàn hệ thống là production-ready. Release public là **NO-GO**
cho tới khi auth middleware thật được nối và account export/delete/retention có
quyết định sản phẩm/pháp lý rõ ràng.

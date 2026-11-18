# Báo cáo Gỡ bỏ Tích hợp Zep Cloud (Chuyển hoàn toàn sang PostgreSQL Local Memory)

- **Ngày thực hiện:** 2026-11-18
- **Quyết định sản phẩm:** Dự án không sử dụng Zep nữa và không thay thế bằng dịch vụ memory ngoài khác.
- **Branch / HEAD baseline:** `main` @ `9730e282bf0e16f6fea3db2fee301173017820a8` (giữ nguyên thay đổi có sẵn của người dùng trên `README.md`, báo cáo reassessment 17/11 và toàn bộ thay đổi Đợt 4 chưa commit)
- **Trạng thái bàn giao:** **Đã gỡ tích hợp Zep ở source và kiểm thử liên quan; memory local PostgreSQL được giữ lại; chưa deploy hệ thống hiện hữu.**

---

## 1. Phân loại và Danh mục Thành phần Đã gỡ

### 1.1 Đã xóa hoàn toàn (chỉ phục vụ Zep — Nhóm A)
- **Adapter & Sync modules:**
  - Xóa `backend/src/memory/zep_memory.py`
  - Xóa `backend/src/memory/sync.py`
- **Dependency & Template cấu hình:**
  - Gỡ `zep-cloud>=3.28.0,<4.0.0` khỏi `backend/requirements.txt` (không có Python lockfile riêng; không uninstall package toàn cục trên host).
  - Gỡ toàn bộ biến `ZEP_MEMORY_ENABLED`, `ZEP_API_KEY`, `ZEP_ID_SECRET`, `ZEP_HTTP_TIMEOUT_SECONDS`, `ZEP_ALLOW_DEV_IDENTITY` khỏi `backend/.env.example` (giữ `CHAT_RETENTION_DAYS=7`; không đọc hay sửa env riêng).
- **API routes chỉ phục vụ external memory (nay trả HTTP `404`):**
  - Gỡ `PUT /me/memory-consent` và `DELETE /me/memory` khỏi `backend/src/api/personalization.py` (cùng `MemoryConsentRequest`, `_require_trusted_memory_identity`).
  - Gỡ `POST /me/memory/sync` khỏi `backend/src/api/memory.py`.
  - **Cam kết hành vi:** Không âm thầm đổi `DELETE /me/memory` thành xóa toàn bộ bộ nhớ PostgreSQL; không trả thành công giả cho thao tác sync/delete ngoài đã bỏ.
- **Đường chat, Graph, State, Composer & Cache:**
  - Gỡ `_memory_identity_allowed` và tham số `use_zep_memory` khỏi `backend/src/api/app.py`, `backend/src/memory/chat.py`, `backend/src/agents/graph.py`, `backend/src/jobs/tasks.py`.
  - Gỡ khối recall `ZepMemory` khỏi `backend/src/agents/graph.py`.
  - Gỡ `memory_context` khỏi `backend/src/agents/state.py`, `backend/src/agents/composer.py` và `backend/src/core/response_cache.py` (sau khi xác minh `memory_context` chỉ vận chuyển kết quả recall Zep, trong khi confirmed local facts đi qua `personalization_context["confirmed_memory"]`).
- **Service consent ngoài & Background job ngoài:**
  - Gỡ `grant_external_memory_consent`, `revoke_external_memory_consent`, `mark_external_memory_deleted` khỏi `backend/src/persistence/personalization_service.py`.
  - Gỡ lời gọi `maintain_external_memory()` khỏi task `jobs.tasks.purge_memory` trong `backend/src/jobs/tasks.py`.
- **Tests chỉ kiểm SDK/adapter Zep:**
  - Xóa `backend/tests/unit/test_zep_memory.py`
  - Xóa `backend/tests/integration/test_zep_sdk_contract.py`
  - Gỡ các test Zep-only trong `backend/tests/unit/test_memory_contract.py` và `backend/tests/unit/test_personalization_api.py`, thay bằng regression cho hành vi local memory và route `404`.

### 1.2 Frontend
- Kiểm kê `frontend/src/` xác nhận frontend không có control UI, type hay API call nào cho `/me/memory-consent`, `/me/memory/sync` hay `DELETE /me/memory`; chỉ gọi các endpoint local `/me/memory/facts`, `/me/memory/facts/{id}/confirm`, `/me/memory/facts/{id}` và đọc trường `data.items`. Không cần sửa `frontend/src/`.

---

## 2. Chức năng Local Memory PostgreSQL Được Giữ Nguyên (Nhóm B)

- **Phiên hội thoại & lịch sử server-side:** `POST /me/conversations`, `GET/DELETE /me/conversations/{conversation_id}`, giới hạn 20 phiên/user, 40 message/phiên, 10 message & 6.000 ký tự context, bỏ qua `history`/`user_id` do client tự gửi, kiểm ownership chặt theo `current_user.subject`.
- **Memory facts local:** `GET/POST /me/memory/facts` (trả `{"items": [...]}`), `POST /me/memory/facts/{id}/confirm`, `DELETE /me/memory/facts/{id}`, đề xuất tự động gắn với `source_message_id` của chính lời user, hạn 7 ngày (pending) / 180 ngày (confirmed), tối đa 40 đề xuất / 20 confirmed facts, lọc injection trước khi đưa vào `confirmed_memory` và composer prompt.
- **Personalization P1:** Profile, measurements, goals, plans, check-ins, `event_context`, `answer_memory_question` (`fast_path="personal_memory"`).
- **Retention/Purge local:** Celery Beat `memory-retention-daily` vẫn chạy `jobs.tasks.purge_memory` -> `memory.store.purge_expired()` để dọn `ChatMessage`, `ChatTask`, `MemoryFact` hết hạn và `ChatSession` rỗng với khóa `User.with_for_update()`.
- **An toàn, Cache & Đợt 1–4:** Urgent fast-path bypass DB/history/queue/LLM/RAG, tool-only BMI fast-path, `is_cacheable_public_rag_request` từ chối cache mọi request có `user_id` hoặc `personalization_context`/`confirmed_memory`, cùng toàn bộ kiểm chứng Đợt 1–4.

---

## 3. Xử lý Consent, Metadata Legacy & Tình trạng Dữ liệu Phía Zep (Nhóm C)

### 3.1 Consent local & tương thích dữ liệu cũ trong DB
- `DEFAULT_CONSENT` và `_consent(user)` trong `backend/src/persistence/personalization_service.py` chỉ còn hai consent hoạt động: `health_data_processing` và `personalization`.
- Gỡ ràng buộc cũ “phải xóa external memory trước khi thu hồi `health_data_processing`/`personalization`” trong `update_profile`. Người dùng có bản ghi DB cũ chứa `external_memory: true` vẫn thu hồi được consent local bình thường.
- `_save_consent(user, flags)` giữ nguyên mọi khóa JSON legacy đã có trong `users.consent_flags` (`external_memory`, `external_memory_sync_pending`, `external_memory_deletion_pending`, `external_memory_consented_at`, `external_memory_synced_at`, `external_memory_revoked_at`, `external_memory_deleted_at`) — không crash, không xóa hay viết lại toàn bộ JSON làm mất dấu vết audit, không gọi mạng hay bật lại scheduler.
- Không drop bảng/cột và không sửa migration đã áp dụng (`infra/database/migrations/20260929_02_memory.up.sql`).

### 3.2 Tình trạng dữ liệu phía nhà cung cấp Zep (tuyên bố bắt buộc)
- **Gỡ code không chứng minh dữ liệu từng gửi sang Zep (nếu có) đã được xóa ở phía nhà cung cấp Zep.**
- Trong task này: không gọi API Zep để xác minh hay xóa dữ liệu; không tự ghi `external_memory_deleted_at` mới; không tự đổi `external_memory_deletion_pending` thành `false`.
- Bổ sung helper đọc-only `legacy_external_memory_status(consent_flags)` trả về `"unverified_external_state"` cho mọi tài khoản còn dấu vết từng bật/đồng bộ external memory (và `"none"` nếu chưa từng có dấu vết).
- **Hướng cleanup về sau (tách riêng, chưa thực hiện):** Nếu vận hành xác nhận có dữ liệu thật từng đồng bộ lên Zep, cần thực hiện quy trình độc lập gồm backup DB, xuất danh sách tài khoản có `legacy_external_memory_status == "unverified_external_state"`, xác nhận đóng/xóa tài khoản ở phía nhà cung cấp Zep (nếu từng kích hoạt), sau đó mới chạy migration dọn các khóa `external_memory*` trong `users.consent_flags` sau khi review.

---

## 4. Phân loại Tham chiếu Còn Lại Sau Khi Gỡ

Rà soát lại bằng `git grep -i -n -E "zep|external_memory|use_zep_memory|memory-consent|memory/sync|memory_context"` trên mã nguồn và cấu hình hoạt động:

| Nhóm tham chiếu còn lại | Vị trí | Phân loại & Lý do giữ |
|---|---|---|
| `backend/src/persistence/personalization_service.py` (`_LEGACY_EXTERNAL_MEMORY_KEYS`, `legacy_external_memory_status`) | Source backend | **Compatibility / Read-only audit** — nhận diện dấu vết JSON legacy trong DB mà không gọi mạng hay bật tính năng đã bỏ |
| `backend/src/rag/corpus_policy.py` (`"zep_memory"` trong tập `source` bị cấm) | Source backend | **Privacy defense-in-depth** — tiếp tục chặn tài liệu legacy mang `source="zep_memory"` xâm nhập shared RAG corpus |
| `infra/database/migrations/20260929_02_memory.up.sql` | Migration lịch sử | **Migration đã áp dụng** — giữ nguyên lịch sử schema DB, không sửa/drop |
| `backend/src/memory/README.md`, `backend/README.md`, `docs/implementation-roadmap/08-...`, `09-...`, `README.md`, `docs/reports/upgrade-2026/*` | Tài liệu hiện hành & lịch sử | Tài liệu hiện hành ghi rõ đã gỡ Zep và dùng PostgreSQL; tài liệu `08`/`09` được gắn ghi chú lịch sử (không xóa biên bản audit/reassessment cũ) |
| `frontend/tests/regression-r04-r05-r10-r11.test.mjs` (dòng 307 mock response) | Test frontend | Giữ nguyên mock tương thích payload cũ (không ảnh hưởng `fetchMemoryFacts`) |
| **SDK import / `zep-cloud` / `ZEP_*` / `use_zep_memory` / remote scheduler** | Toàn bộ `backend/src`, `requirements.txt`, `.env.example`, `docker-compose.yml`, `frontend/src` | **0 tham chiếu** |

---

## 5. Kết quả Kiểm thử & Phần Chưa Kiểm chứng

| Hạng mục | Môi trường | Lệnh chạy | Kết quả |
|---|---|---|---|
| Kiểm tra import/khởi động không có SDK & env Zep (`test_app_imports_and_starts_without_zep_sdk_or_zep_env`) | **Subprocess Python cô lập** chèn `BlockZep` vào `sys.meta_path` (chặn `zep_cloud`, `memory.zep_memory`, `memory.sync`) và xóa toàn bộ biến `ZEP_*` | Nằm trong `backend/tests/unit/test_local_memory_without_zep.py` | **PASS** (exit 0, chứng minh ứng dụng không phụ thuộc package Zep trên host) |
| Suite regression local memory mới (`test_local_memory_without_zep.py` — 6 test) | SQLite in-memory + `socket.create_connection` bị chặn (0 outbound network) + FastAPI TestClient | Chạy cùng backend suite | **6 passed**, 0 failed (kiểm local facts lifecycle, owner isolation, sync/async chat, legacy flags & local consent revoke, routes 404 không xóa local memory, urgent/tool-only/cache) |
| Toàn bộ backend unit + fast-path integration + local Qdrant integration | SQLite in-memory + fake/mock upstream + `QdrantClient(":memory:")` | `$env:PYTHONPATH=(Resolve-Path 'backend/src').Path; $env:DATABASE_URL='sqlite://'; python -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py backend/tests/integration/test_phase04_qdrant_local_lifecycle.py -q -p no:cacheprovider` | **326 passed**, 0 failed (3 warnings: 2 `on_event` cũ + 1 local Qdrant payload index warning) |
| Data pipeline tests | Synthetic fixtures | `python -m pytest data_pipeline/tests -q -p no:cacheprovider` | **13 passed**, 0 failed |
| Python 3.10 grammar & syntax check | Static AST (`feature_version=(3, 10)`) + `py_compile` | 16 file sửa/mới | **PASS (16/16 files)** |
| Diff hygiene | Git working tree | `git diff --check -- backend/ data_pipeline/ docs/` | **PASS (0 lỗi)** |
| Runtime HTTP thật / PostgreSQL thật / Celery worker & Beat container / Docker build image không có `zep-cloud` | Docker daemon không chạy trên host | — | **NOT_RUN** — kết quả TestClient/SQLite không thay thế kiểm chứng runtime PostgreSQL/Celery/HTTP production |

---

## 6. File Thay đổi & Hướng Rollback Source

### File đã xóa
1. `backend/src/memory/zep_memory.py`
2. `backend/src/memory/sync.py`
3. `backend/tests/unit/test_zep_memory.py`
4. `backend/tests/integration/test_zep_sdk_contract.py`

### File mới
5. `backend/tests/unit/test_local_memory_without_zep.py`
6. `docs/reports/upgrade-2026/remove-zep-2026-11-18.md`

### File đã sửa
7. `backend/requirements.txt`
8. `backend/.env.example`
9. `backend/README.md`
10. `backend/src/memory/README.md`
11. `backend/src/memory/store.py`
12. `backend/src/memory/chat.py`
13. `backend/src/persistence/personalization_service.py`
14. `backend/src/api/memory.py`
15. `backend/src/api/personalization.py`
16. `backend/src/api/app.py`
17. `backend/src/agents/state.py`
18. `backend/src/agents/graph.py`
19. `backend/src/agents/composer.py`
20. `backend/src/core/response_cache.py`
21. `backend/src/jobs/tasks.py`
22. `backend/src/rag/corpus_policy.py`
23. `backend/tests/unit/test_memory_contract.py`
24. `backend/tests/unit/test_personalization_api.py`
25. `backend/tests/unit/test_llm_response_cache.py`
26. `backend/tests/unit/test_phase02_claim_and_provenance.py`
27. `docs/implementation-roadmap/08-zep-memory-integration-2026-09-29.md`
28. `docs/implementation-roadmap/09-day17-memory-completion-2026-09-29.md`
29. `docs/implementation-roadmap/README.md`

### Hướng rollback (chỉ trong phạm vi source)
- Vì không sửa schema PostgreSQL, không xóa dữ liệu và không thay đổi migration, toàn bộ thay đổi gỡ Zep có thể rollback bằng `git` trên danh sách file trên mà không mất dữ liệu local hay thay đổi của các đợt trước. Tuy nhiên, nếu cần bật lại bất kỳ external memory nào trong tương lai, phải mở quy trình thiết kế/privacy/consent riêng thay vì phục hồi cấu hình cũ.

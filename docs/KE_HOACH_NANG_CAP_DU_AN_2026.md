# Kế hoạch nâng cấp Health/InBody Agent RAG năm 2026

**Phiên bản 3.0 — quyết định kiến trúc ngày 2026-11-05:** Chỉ phát triển backend gộp tại backend/src. Không tiếp tục Profile B, Core API và Agent Service tách rời. Đây là kế hoạch cho coding agent, không phải chứng nhận production.

**Đích:** RAG beta có bằng chứng, an toàn y tế và quyền sở hữu dữ liệu đúng; chỉ xét Production Candidate sau khi qua các gate ở mục 8.

## 1. Cách dùng và mức bằng chứng

Đọc AGENTS.md, docs/implementation-roadmap/README.md, SETUP.md và README của component được sửa. Hai báo cáo P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md và P1_PERSONALIZATION_REPORT.md đang bị xóa sẵn trong working tree; giữ nguyên, không tự khôi phục. Dùng source, test và roadmap còn hiện hữu để đối chiếu.

| Nhãn | Ý nghĩa |
|---|---|
| VERIFIED_SOURCE | Đã đối chiếu call path và code hiện tại; chưa chứng minh chạy đúng |
| VERIFIED_TEST | Test đã thực thi đạt trong môi trường được ghi rõ |
| VERIFIED_RUNTIME | Process/HTTP/dependency thật đã nhận revision và config đã ghi |
| SOURCE_READY | Source và test liên quan đạt; chưa deploy |
| NOT_RUN | Chưa chạy; không suy ra đạt |
| BLOCKED | Không thể hoàn thành gate; nêu điều kiện gỡ chặn |

Mỗi đợt chỉ làm một work package (WP) hoặc lát cắt được ghi rõ. Viết regression tái hiện trước, sửa tại owner đúng, chạy test, kiểm tra diff, rồi mới deploy có kiểm soát nếu cần. Cập nhật mục 10 sau mỗi WP. Không stage/commit/push nếu chưa được yêu cầu.

## 2. Kiến trúc duy nhất và đường đi thực

| Thành phần | Điểm vào | Vai trò |
|---|---|---|
| Frontend | frontend/src/lib/api.ts | Gọi API cổng 8000; không quyết định quyền sở hữu bằng user_id client |
| Backend gộp | backend/docker-compose.yml → backend/src/api/app.py | FastAPI, auth, personalization, chat, Agent, RAG và tools |
| Chat/context | backend/src/memory/chat.py → persistence/personalization_service.py, memory/store.py | Lấy context đã xác nhận, hội thoại theo owner, lịch sử có giới hạn |
| Agent | backend/src/agents/graph.py và agents/nodes/ | Safety fast-path, routing, tools, retrieval, composition |
| Retrieval | backend/src/rag/search.py, rag/qdrant/client.py | BM25/dense Qdrant; embedding từ infra/embed_serving |
| Queue | backend/src/jobs/tasks.py | Celery worker/scheduler cho task đã nối thật |
| Hạ tầng | infra/docker-compose.infra.yml | PostgreSQL, Qdrant, Valkey, BGE-M3 CPU |
| Pipeline | data_pipeline/run_pipeline.py | Corpus dùng chung, import, manifest và kiểm chứng |

Các thư mục core-api/ và agent-service/ cùng docker-compose.microservices.yml đã được rút khỏi đường triển khai theo quyết định mới. contracts/ còn là mã hợp đồng liên service lịch sử, hiện backend không import; không dùng nó làm chuẩn cho API monolith. Các báo cáo WP-00/WP-01 cũ trong docs/reports/upgrade-2026/ chỉ là bằng chứng lịch sử của Profile B, không phải chỉ dẫn triển khai.

Backend gộp đã có phần lớn tính năng cần thiết. Không sao chép code từ service đã rút vào backend nếu chưa chứng minh backend thiếu hành vi đó. Backend/src mới là nguồn chuẩn cho mọi sửa đổi tiếp theo. Thay đổi OCR service đang bị xóa sẵn trong working tree là phạm vi riêng; không tự phục hồi hoặc triển khai OCR từ các file đã xóa.

## 3. Những finding và bất biến cần giữ

### 3.1 Safety, auth và dữ liệu

- Deterministic urgent precheck phải chạy trước LLM, rewrite, retrieval, rerank và web. Urgent trả ngay, không chờ DB/Redis/provider. BMI/tool-only đủ dữ liệu không gọi LLM/search.
- User identity lấy từ server auth context. X-Dev-User-Id chỉ dùng khi AUTH_MODE=development. Production chưa có verifier hoàn chỉnh thì fail closed, không coi client header hay JWT payload chưa xác minh là auth.
- PostgreSQL là nguồn chuẩn của profile, consent, measurement đã xác nhận và hội thoại. Resource theo owner phải trả 404 khi user khác truy cập. Không đưa PII hoặc phiếu InBody cá nhân vào Qdrant corpus dùng chung.
- Memory/chat hiện có trong backend/src/memory. Người dùng không cần mở rộng Zep; trước khi tắt/xóa code Zep cần kiểm kê consent và dữ liệu ngoài cũ để không báo xóa thành công giả.
- Không dùng kết quả LLM để xóa cảnh báo safety. Không chẩn đoán, kê đơn hoặc cam kết kết quả y khoa.

### 3.2 API và response

Giữ API công khai của backend gộp: POST /chat/complete, GET /chat/complete/{task_id}, POST /agent/answer, các route /me, /search và /tools. Không đưa hợp đồng HTTP Core → Agent của Profile B trở lại.

Response Agent cần giữ answer/content, status, fast_path, selected_agents, agent_trace, tool_results, retrieved_docs, evidence/citations, claim_evidence_links, evidence_status, safety_result, errors, latency_ms và các metadata hội thoại đã công bố. Frontend phải map đúng response thật, không tự dựng success từ mock khi backend lỗi. Input sai: 4xx; dependency lỗi: 502/503; timeout: 504 hoặc degraded contract có chủ đích.

Request ID, route, stage, status và latency có thể log; không log nguyên prompt, chỉ số sức khỏe hay secret. Không trả stack trace/URL nội bộ trong errors.

### 3.3 Retrieval/release

- Query gốc là truy vấn retrieval đầu tiên; tool-only không gọi RAG. Safety query filter/boost medical_safety và không có recipe trong top 5.
- Không gọi hệ thống hybrid nếu sparse/BM25 chưa thực sự tham gia. Snapshot BM25 hiện được nạp vào RAM mỗi process; cần đo và chọn shared/persistent architecture trước khi tăng worker.
- Import idempotent với stable ID/content hash, fail closed khi embedding thiếu vector. Collection mới phải versioned; alias blue/green chỉ đổi sau point count, manifest, retrieval/eval gate. Không xóa/ghi đè collection đang phục vụ.
- Một request phải dùng cùng corpus/release identity cho dense, lexical và response cache. Nếu identity không xác minh được thì tắt cache câu trả lời.

## 4. Thứ tự work package cho backend gộp

| Đợt | WP | Gate để chuyển tiếp |
|---|---|---|
| 0 | WP-00, WP-01 | Chốt backend gộp, gỡ cấu hình split, kiểm tra baseline và runtime hiện có |
| 1 | WP-02, WP-03, WP-04 | Context/hội thoại, auth/safety boundary và UI thật đúng contract |
| 2 | WP-06, WP-07 | Import fail-closed và release Qdrant/lexical có rollback |
| 3 | WP-05, WP-08, WP-09 | Tối ưu graph, retrieval, reranker, cache chỉ sau benchmark |
| 4 | WP-10, WP-11 | Citation/OCR và DB lifecycle có bằng chứng |
| 5 | WP-12 | HTTP, holdout, latency, soak, privacy và release decision |

### WP-00 — Baseline backend gộp

**Files:** backend/src/api/app.py, backend/docker-compose.yml, backend/.env.example, backend/src/agents/graph.py, backend/src/memory/chat.py, infra/docker-compose.infra.yml.

1. Ghi HEAD, git status, config không chứa secret, container/listener hiện có, import job và Qdrant collection/alias/point count trước mọi restart.
2. Ghi endpoint đang được frontend gọi; phân biệt process TestClient, image, container và HTTP runtime.
3. Chạy baseline unit suite và test HTTP read-only trên backend hiện chạy. Không dùng số liệu Profile B làm baseline backend gộp.

**Gate:** Có revision/config/corpus identity và số liệu trước sửa; không còn giả định hai deployment profile cùng là đích.

### WP-01 — Gỡ hướng tách service

**Files:** core-api/, agent-service/, docker-compose.microservices.yml, ARCH.MD, kế hoạch này. Giữ backend/src, backend/docker-compose.yml, frontend, infra và data_pipeline.

1. Kiểm kê consumer/ignored file trước khi xóa; không xóa OCR, volume, corpus hoặc thay đổi người dùng ngoài phạm vi.
2. Gỡ hai thư mục service và Compose liên service; không tự khôi phục các file đã bị xóa trong working tree.
3. Đánh dấu báo cáo Profile B là lịch sử. Kiểm tra backend không import contracts liên service, Core hoặc Agent Service.
4. Chạy syntax, backend unit selection và Compose config. Nếu deploy backend gộp: preflight import và HTTP smoke sau deploy riêng.

**Gate:** Không còn entrypoint/service split trong cấu hình triển khai chính; backend gộp import/test được. Xóa source không chứng minh runtime backend gộp đã restart.

### WP-02 — Context, conversation và response trong backend gộp

**Files:** backend/src/api/app.py, backend/src/memory/chat.py, store.py, context.py, backend/src/persistence/personalization_service.py, backend/src/agents/graph.py. Frontend adapter thuộc WP-04 theo quyết định chỉ làm trong backend.

1. Lấy fixture thật từ safe_build_confirmed_context: profile, measurement confirmed mới nhất, active goal, provenance object, consent và reason unavailable. Không suy birth_year/sex từ age_range/sex_at_birth khi thiếu.
2. Kiểm tra context được chuyển đầy đủ vào AgentState và composer. latest_measurement cũ chỉ là compatibility, không được thay thế dữ liệu confirmed bằng bản chưa xác nhận.
3. conversation_id có sẵn phải lookup theo owner trước load/history/persist; ID người khác trả 404. ID thiếu thì server tạo ID dùng được cho lượt sau khi policy cho phép.
4. Lịch sử do server load/bound; history client chỉ là input compatibility và không được dùng như nguồn tin cậy. Ghi user+assistant trong cùng transaction theo owner; DB failure trả memory_status/limitations rõ, không báo đã lưu.
5. Giữ metadata response từ graph tới /chat/complete và /agent/answer; test error/degraded, task async, request ID và conversation ID round-trip. Việc dùng lại conversation ID ở frontend thuộc WP-04.

**Regression:** context off/consent off; profile có/không conditions; measurement confirmed/unconfirmed/deleted; active goal; provenance object; conversation A/B; history spoof; DB failure sau inference; metadata/citation round-trip.

**Gate:** Fixture builder thật đi qua API → memory.chat → AgentState → response backend không mất thông tin hoặc đổi nghĩa. Frontend adapter nghiệm thu ở WP-04.

### WP-03 — Auth, ownership và safety tại public API

**Files:** backend/src/auth/context.py, api/app.py, api/personalization.py, api/memory.py, agents/graph.py, agents/fast_paths.py, health/tools.py, backend/docker-compose.yml.

1. Chọn và nối verifier production thật; JWT phải kiểm signature/issuer/audience/expiry/algorithm allowlist nếu dùng JWT. Không tạo issuer giả để làm pass.
2. Dev header chỉ hoạt động trong explicit development mode. Kiểm tra spoof, owner A/B ở mọi route family, corpus admin và Celery task owner.
3. Urgent ở public boundary không chờ DB/context hoặc task async; injection không che dấu hiệu cấp cứu. Safety tool result không bị composer làm mất.
4. Rate limit shared, CORS allowlist, liveness/readiness thật và deadline tổng; không chạy sync inference trong async event loop.

**Gate:** 0 cross-user leak/unauthorized side effect; urgent/BMI zero forbidden dependency calls; HTTP latency được đo riêng WP-12.

### WP-04 — Frontend dùng API thật và lỗi thật

**Files:** frontend/src/lib/api.ts, frontend/src/types/index.ts, các component chat/profile/InBody/OCR; backend/src/api/app.py và schemas tương ứng khi contract cần sửa.

1. Bỏ fallback mô phỏng ngầm cho chat, profile, measurement, OCR, search và save/delete. Offline/degraded/error có UI tiếng Việt rõ; không tạo trace, citation, confidence hoặc dữ liệu giả.
2. Map measurement schema thật: smm_kg, bfm_kg, pbf_percent, source_type, confirmed_by_user; OCR extracted_fields là draft cần user xác nhận.
3. Không dùng user_id từ localStorage làm auth production. Bảo đảm timeout frontend lớn hơn hard timeout backend, conversation ID được dùng lại đúng phiên.
4. Escape source/title/content từ Qdrant; giữ DevTools/System ẩn ở production.

**Gate:** Browser test và HTTP thật chứng minh lỗi backend không hiển thị thành success hoặc dữ liệu mock.

### WP-05 — Tinh gọn graph có điều kiện

Đo stage/route/LLM/retrieval P50/P95 trước. Chỉ hợp nhất node khi test chứng minh giảm độ trễ mà không đổi selected_agents, safety, trace, tool_results và citation. Không đặt normalize có LLM trước deterministic precheck.

### WP-06 — Import fail-closed và release manifest

Ở data_pipeline và backend/src/rag: phát hiện thiếu embedding/vector, content hash đổi, duplicate chunk ID, verify-stage fail; tất cả phải trả exit code lỗi và manifest truy vết được. Không gọi green là đủ corpus. Test dry-run/partial failure/idempotency trên collection staging.

### WP-07 — Blue/green Qdrant + BM25/cache

Tạo collection version mới, index payload, đối chiếu expected unique points và sample retrieval. Pin BM25 snapshot/corpus version/cache identity cùng release; rehearsal promote/rollback. Trước swap ghi job status, old alias, point count, manifest và log cuối. Không động collection đang phục vụ nếu chưa có rollback.

### WP-08 — Recipe policy, retrieval và reranker

Chốt eval set/corpus version; test safety filter và recipe false positive. Reranker CPU chỉ bật nếu cải thiện MRR/NDCG, latency và tài nguyên chấp nhận được. Không so benchmark khác corpus hoặc tuyên bố accuracy từ smoke nhỏ.

### WP-09 — Cache có bằng chứng

Kiểm tra policy cache hiện có trên Redis thật: eligibility, hit/miss, user context exclusion, corpus version invalidation, TTL và lỗi Redis. Không cache response cá nhân/clinical/urgent hoặc answer thiếu evidence.

### WP-10 — Citation và OCR

Claim-evidence links phải trỏ document thật đã retrieve, kèm source/provenance; nếu context yếu thì báo thiếu. OCR chỉ mở sau khi OCR service hiện diện và được kiểm chứng; flow upload → draft → user confirm → owner-scoped save. Không lấy confidence hằng ở UI làm accuracy.

### WP-11 — DB lifecycle và memory không dùng Zep mới

Audit live schema/migrations/consent/retention trước migration nhỏ. Không thêm hệ memory thứ hai. Nếu quyết định ngừng Zep legacy trong backend, trước hết kiểm kê consent/dữ liệu cloud, thiết kế thu hồi/xóa fail-closed và test, không báo xóa hoàn tất trước provider xác nhận.

### WP-12 — Nghiệm thu và deploy

Chạy HTTP smoke, holdout retrieval/citation/safety, load/soak, privacy/owner và rollback trên revision/config/corpus đã pin. Tách kết quả source, test, container và runtime. Không gọi production-ready nếu còn P0/P1 hoặc chưa có auth production.

## 5. Runbook cho coding agent

PowerShell tại repo root, không lồng core-api/agent-service vào PYTHONPATH:

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH="$((Resolve-Path 'backend/src').Path);$((Get-Location).Path)"
$env:DATABASE_URL='sqlite://'
$env:LLM_PROVIDER='none'
$env:BM25_AUTOLOAD='false'
$env:FEATURE_OCR_UPLOAD='false'
python -B -m pytest backend/tests/unit -q -p no:cacheprovider --basetemp=.tmp-backend-unit
python -B -c "import ast,pathlib; files=['backend/src/api/app.py','backend/src/agents/graph.py','backend/src/memory/chat.py']; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'),filename=p) for p in files]; print('syntax OK')"
docker compose -f infra/docker-compose.infra.yml config --quiet
docker compose -f backend/docker-compose.yml config --quiet
git diff --check
~~~

Nếu backend/.env hoặc credential bắt buộc thiếu, báo thiếu; không điền giá trị giả để làm config pass. Dùng temp trong workspace và dọn đúng artifact do lượt chạy tạo. Windows sandbox có thể chặn socketpair/TestClient hoặc temp mặc định; phân loại lỗi môi trường riêng, không coi là lỗi app.

**Trước restart/import/alias:** ghi Qdrant point count, collection/alias status, import process/job, manifest/log cuối, container revision/config và phương án rollback. Không restart embedding/backend khi bulk import đang chạy trừ khi chủ động chấp nhận dừng job.

**HTTP tối thiểu sau deploy:** /health; chào hỏi; BMI 72 kg/170 cm; đau ngực + khó thở; InBody; nutrition; exercise; safety retrieval; input âm trả 422; owner A/B; dependency down; frontend error/degraded. Không dùng TestClient thay thế HTTP của container đang chạy.

## 6. Quality gates

| Gate | Điều kiện |
|---|---|
| Urgent và BMI/tool-only | P95 HTTP < 500 ms từng nhóm; zero LLM/search/rewrite/rerank/web calls |
| Request chuẩn | Không vượt 60 giây; timeout/degraded có mã lỗi rõ |
| Router | Accuracy ≥ 95%, không route rỗng trên eval set đã khóa |
| Retrieval | Recall@5 ≥ 90%; strict top-1 relevance ≥ 75% |
| Safety retrieval | Hit@5 = 100%; recipe trong safety top 5 = 0 |
| Citation | Precision ≥ 95% với reviewer/claim support, không chỉ marker |
| Auth/owner | 0 cross-user leak/unauthorized side effect; production verifier và rate limit hoạt động |
| Operations/UI | Soak không OOM/restart; rollback diễn tập; không lỗi visual/accessibility nghiêm trọng |

Các ngưỡng là mục tiêu, chưa phải kết quả. Ghi N, corpus/release, model, device/dtype, batch, latency và nhóm query. Nếu thiếu nhãn relevance/reviewer thì NOT_MEASURED, không dùng similarity thay thế.

## 7. Mẫu giao việc

~~~text
Thực hiện WP-<ID> trong docs/KE_HOACH_NANG_CAP_DU_AN_2026.md.
Entrypoint duy nhất: backend/src/api/app.py; deployment: backend/docker-compose.yml.
Bug/behavior và case tái hiện: <...>.
Revision, working-tree delta, corpus/config: <...>.
Files được sửa: <...>. Không sửa split service đã rút.
Viết regression trước, sửa đúng owner, chạy unit/integration không phá dữ liệu.
Trước restart ghi import job/Qdrant preflight, rồi HTTP sau deploy nếu được giao.
Báo VERIFIED_SOURCE/TEST/RUNTIME riêng, lỗi/rollback và phần NOT_RUN.
Không reset, stage, commit, push hoặc sửa thay đổi sẵn có.
~~~

## 8. Definition of Done

- Có case tái hiện/characterization và test liên quan đạt; syntax/diff không lỗi.
- Contract, negative/dependency failure, safety/owner và privacy được kiểm tra theo phạm vi.
- Runtime chỉ được gọi đạt khi đúng revision/config nhận code mới, có HTTP sau deploy và số liệu trước/sau.
- Docs/tiến độ cập nhật; blocker nêu rõ. Source-ready không đồng nghĩa runtime đã sửa.

## 9. Bằng chứng lịch sử và giới hạn

Baseline chọn lọc trước khi đổi hướng: 34 backend/data-pipeline tests passed trên Python host 3.13. Đây không phải full suite, HTTP backend gộp, auth production hoặc RAG accuracy. WP-00/WP-01 Profile B đã từng build/test và chạy thử trên volume test; kết quả đó chỉ thuộc kiến trúc đã rút, không dùng làm chứng cứ backend gộp. Không có xác nhận mới rằng backend gộp đang chạy sau lần xóa service.

## 10. Tiến độ triển khai

| Hạng mục | Source | Test | Runtime | Việc tiếp theo |
|---|---|---|---|---|
| Quyết định backend gộp 2026-11-05 | Hai thư mục split đã deleted trong working tree; Compose split đã gỡ; tài liệu đổi hướng | Backend unit 142/142 passed trên Python host 3.13, SQLite in-memory; hai Compose config đạt | NOT_RUN HTTP backend gộp sau đổi hướng | Đã gỡ container/image ứng dụng Profile B và container hạ tầng test đã dừng; giữ nguyên ba volume wp01_* và thay đổi OCR/user |
| WP-00 monolith baseline | Đã đối chiếu entrypoint backend/src/api/app.py và các owner chính | 142 unit passed; baseline chọn lọc lịch sử 34 passed | NOT_RUN HTTP hiện tại | Ghi HEAD/config/corpus/runtime trước deploy |
| WP-01 gỡ split | SOURCE_READY: không còn hai thư mục/Compose split; backend import với SQLite test | 142 unit passed; syntax và git diff --check đạt | Hai container/image Profile B đã gỡ; backend gộp chưa restart | Nếu deploy backend gộp: preflight import/Qdrant và HTTP smoke |
| WP-02 context/conversation/response | Đã sửa tạo phiên lỗi thành degraded, phân biệt lỗi proposal và lỗi ghi transcript; context chọn mục tiêu active mới nhất; request ID ở hai API. Dockerfile chuyển sang Bookworm, bỏ bốn dependency llama-index không dùng | Backend unit 152/152 passed sau WP-03; fixture builder thật qua /agent/answer, consent, owner/history spoof và lỗi ghi sau inference | VERIFIED_RUNTIME trên stack Docker thử nghiệm biệt lập: HTTP backend ↔ PostgreSQL/Qdrant/BGE-M3 CPU; conversation 1 session/4 messages, owner B 404, Qdrant 2 point tổng hợp. Xem [báo cáo](reports/upgrade-2026/wp02-monolith-runtime-2026-11-05.md) | Chưa deploy Compose/volume hiện hữu; LLM và corpus thật chưa nghiệm thu |
| WP-03 auth/safety boundary | SOURCE_READY: auth nội bộ Argon2id + JWT HS256 xác minh chữ ký/issuer/audience/expiry; header dev chỉ ở development; CORS allowlist; readiness dependency probe; urgent async bypass Celery; rate limit Redis cho register/login | VERIFIED_TEST: 152 backend unit passed, gồm JWT forged/expired/wrong audience, auth flow, rate limit và urgent/readiness. Image `bodywise-backend:wp03-source` build và import closure đạt; `git diff --check` đạt | VERIFIED_RUNTIME **chỉ trên stack test biệt lập**: PostgreSQL/Redis + backend host HTTP; unauth/dev header 401, đăng ký/đăng nhập 201/200, forged 401, spoof user_id 403, owner A 200/B 404, consent false, urgent fast-path 200 (một mẫu 13 ms), rate limit lần 6 trả 429; readiness 503 khi Qdrant/embedding vắng. Xem [báo cáo](reports/upgrade-2026/wp03-wp04-auth-ui-2026-11-05.md) | Chưa migration/deploy volume hiện hữu; chưa kiểm tất cả route family, rate limit ngoài auth, revoke token, browser E2E, P95/soak; không gọi production-ready |
| WP-04 frontend thật | SOURCE_READY: SCR-01–SCR-07 giữ UI sáng; auth form với JWT chỉ trong RAM, logout; production không dùng dev header/demo/đổi API URL; profile không tự nhận consent/giới tính/chiều cao; goal đọc/ghi API thật; measurement không tự tạo id/score/weight; chat giữ conversation_id; OCR timeout 110s | VERIFIED_TEST: ESLint 0 error/0 warning, tsc 0 error, Next.js 16 production build 4/4 static pages | VERIFIED_RUNTIME **một phần**: Next `localhost:3000` trả HTTP 200 và HTML có form đăng nhập; backend test HTTP auth/CORS đạt. Browser control timeout nên chưa chứng minh thao tác đăng nhập và dữ liệu thật trong browser; ảnh responsive cũ thuộc revision trước thay đổi JWT | Cần browser E2E sau deploy cùng revision/config, kiểm UI error/degraded và accessibility; không dùng ảnh cũ làm bằng chứng màn hình mới |
| WP-05–WP-12 | Chưa nghiệm thu | NOT_RUN | NOT_RUN | Theo thứ tự mục 4 và gate mục 6 |

Không sửa trạng thái thành hoàn tất chỉ vì code đã tồn tại. Báo cáo split cũ phải đọc như lịch sử, không làm chỉ dẫn deploy.

Lần thử HTTP local ban đầu dùng SQLite bị timeout phía client và WinError 64 của Windows socket, không tính là runtime pass. Lần kiểm thử Docker biệt lập sau đó xác nhận HTTP với PostgreSQL/Qdrant/embedding thật như báo cáo WP-02. Lần WP-03 dùng Postgres/Redis disposable và backend host, không phải image/Compose sản phẩm. Không có chứng cứ browser E2E do công cụ điều khiển Chrome timeout, hoặc provider LLM/corpus thật/volume sản phẩm sau thay đổi này.

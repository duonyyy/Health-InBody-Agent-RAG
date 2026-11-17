# Kế hoạch sửa code sau rà soát ngày 2026-11-17

**Trạng thái: FIX-01–04 SOURCE_READY; FIX-05 chờ runtime.** Sau FIX-04, 267 backend tests, frontend lint/TypeScript và hai build sentinel + build khôi phục đạt; 8 HTTP checks CORS/JWT/build env biệt lập đạt. Chưa deploy container hoặc nghiệm thu dependency/browser thật. Xem [báo cáo FIX-01](reports/upgrade-2026/fix01-health-input-2026-11-17.md), [FIX-02](reports/upgrade-2026/fix02-greeting-safety-2026-11-17.md), [FIX-03](reports/upgrade-2026/fix03-frontend-dependencies-2026-11-17.md) và [FIX-04](reports/upgrade-2026/fix04-deployment-config-2026-11-17.md).

Nguồn: [báo cáo rà soát](reports/upgrade-2026/project-review-2026-11-17.md), revision `a024500` và source hiện tại. Tài liệu này bổ sung kế hoạch nâng cấp 2026, xử lý F1–F6 trước các WP tối ưu tiếp theo.

## 1. Phạm vi, quyết định và baseline

- Tiếp tục backend gộp tại `backend/src`, frontend Next.js hiện có, PostgreSQL/Qdrant/Valkey/BGE-M3. Giữ ba specialist hiện hành và định danh công khai của chúng.
- Không mở rộng Zep, tạo agent/service mới, thay corpus hoặc đổi model để xử lý các lỗi này.
- Theo từng đợt: regression đỏ → sửa tại owner → test xanh → kiểm tra diff → ghi bằng chứng. Chỉ đổi tài liệu tiến độ khi có kết quả thực thi.
- Working tree khi lập kế hoạch có `README.md` đang sửa và báo cáo rà soát chưa track. Giữ nguyên nội dung ngoài phạm vi; kiểm tra lại status/diff trước mọi chỉnh sửa. Không stage/commit/push theo tài liệu này.
- Baseline đã chạy trong lượt rà soát: 158 backend unit + 3 integration fast-path đạt trên Python host 3.13/SQLite, LLM none; ESLint đạt. Frontend compile/TypeScript/prerender đạt nhưng build command exit 1 do cảnh báo bảo mật. Bốn Compose config hợp lệ.
- Backend image dùng Python 3.10: test host không thay cho kiểm tra image. Docker Engine hiện offline; runtime mới, browser E2E, provider và corpus thật chưa nghiệm thu.

## 2. Thứ tự thực hiện

| Đợt | Finding | Kết quả cần đạt | Điều kiện bắt đầu |
|---|---|---|---|
| FIX-01 | F1 | Đầu vào số sai không thành số đo hợp lệ | Có regression trên parser và hai API chat |
| FIX-02 | F2 | Lời chào không nuốt yêu cầu; risk/trace đúng | FIX-01 đạt để kiểm thử câu hỗn hợp |
| FIX-03 | F5 | Dependency đã vá, frontend build exit 0 | Đọc hướng dẫn Next trong frontend/AGENTS.md |
| FIX-04 | F3, F4, F6 | Cấu hình browser/API/auth/network nhất quán | FIX-03 đạt trước khi build image UI |
| FIX-05 | Gate runtime | Chứng minh luồng thật trên cùng revision/config | Docker sẵn sàng và đã ghi preflight |

Mỗi đợt có diff/test riêng. Chưa đạt một gate thì ghi lỗi và giữ phần phụ thuộc ở NOT_RUN; không báo hoàn thành toàn hệ thống.

## 3. FIX-01 — Bảo toàn và xác thực số đo từ ngôn ngữ tự nhiên

### Owner và files

- `backend/src/agents/parsing.py`: extract_weight_kg, extract_height_cm, extract_pbf, extract_visceral_fat và helper regex.
- `backend/src/agents/fast_paths.py`, `nodes/inbody.py`, `nodes/nutrition.py`, `nodes/training.py`: consumer dùng số đo; rà nơi lấy giá trị từ text rồi fallback context.
- `backend/src/health/validation.py` (file mới nếu chưa có owner phù hợp): quy tắc xác thực đầu vào và exception miền nghiệp vụ, không import FastAPI/DB/LLM. Có thể dùng lại parser qua import lười ở boundary; kiểm tra vòng import trước khi chốt vị trí.
- `backend/src/agents/graph.py`, `backend/src/memory/chat.py`, `backend/src/api/app.py`, `backend/src/api/personalization.py`: gắn validation và mapping lỗi; `backend/src/jobs/tasks.py` chỉ chỉnh nếu propagation task cần thay đổi.
- Tests: `backend/tests/unit/test_agent_parsing.py`, `test_agent_fast_paths.py`, `test_memory_contract.py`, `test_api_boundaries_wp03.py`, `backend/tests/integration/test_api_fast_paths.py`.

### Quyết định hành vi

1. Tách ba trạng thái: không có số đo, có số đo hợp lệ, có số đo tường minh nhưng sai. Không đổi số âm thành dương; không biến số sai thành None rồi lấy số đo đã lưu thay thế.
2. Giữ đúng dấu, đơn vị, dấu phẩy thập phân và dạng 1m70/1m7. Nhận dấu âm ASCII và Unicode thường gặp; không match phần số dương bên trong `-72kg`, `-1m70`, `-170cm`.
3. Quy tắc miền tham chiếu schema API hiện hành: 0 < weight_kg <= 500; 30 <= height_cm <= 300; 0 <= pbf_percent <= 100; 0 <= visceral_fat_level <= 100. Dùng hằng/helper chung cho phạm vi sửa nếu tránh được drift, không refactor mọi schema trong một lượt.
4. Chỉ coi giá trị là số đo hiện tại khi ngữ cảnh thực sự gán số đo. `Tôi muốn giảm 2kg`, `đã giảm -2kg` hoặc câu hỏi giải thích BMI không tự thành cân nặng hiện tại. Nếu không phân giải được nhiều giá trị/mâu thuẫn, hỏi lại và không tính từ một giá trị được chọn tùy tiện.
5. Input xác định rõ là số đo sai trả HTTP 422 ở cả `/agent/answer` và `/chat/complete` sync/async. Response có `detail` tiếng Việt an toàn; có thể thêm `code=invalid_health_input`/tên trường, không trả raw prompt, stack trace hoặc giá trị sức khỏe trong log. FE hiện đọc detail dạng chuỗi nên giữ cách hiển thị này.
6. Thiếu dữ liệu vẫn theo luồng hỏi bổ sung hiện có; không coi mọi câu không có số là 422. Không sửa nguồn câu hỏi chỉ để đáp ứng regex.

### Vị trí và thứ tự xử lý

- Thứ tự bắt buộc: auth/ownership → urgent deterministic precheck → kiểm tra số đo tường minh → DB/history/queue → graph/tools/provider.
- Urgent kèm số đo sai vẫn trả hướng dẫn khẩn cấp trước, không bị HTTP 422 che mất.
- API kiểm tra trước tạo task/dispatch Celery; `run_chat` kiểm tra trước context/open_conversation; direct `multi_agent_handle` có cùng invariant trước greeting/tools. Dùng một helper chung, không sao chép logic validation ba nơi.
- Exception validation phải đi qua `_execute` trong `api/personalization.py` và các `except Exception` trong graph/chat API mà không biến thành 503/500 hoặc deterministic fallback thành công. Map tại FastAPI boundary, không đưa HTTPException vào parser.
- Job đã xếp hàng từ revision cũ cũng kiểm tra lại qua run_chat; đầu vào sai không được task SUCCESS với kết quả BMI giả. Chỉ hứa HTTP 422 ở thời điểm nhận request mới; lỗi job đã chạy vẫn theo failure contract async có sẵn.

### Ma trận nghiệm thu

| Ca | Kỳ vọng |
|---|---|
| 72kg + 170cm; 72,5kg; 1m70; 1,70m; không dấu | Parse đúng; BMI chuẩn 72/1.7² = 24.91 |
| -72kg, −72kg, -170cm, -1m70; 0kg; 501kg; 301cm | Giữ được ý nghĩa invalid; không có tool result hợp lệ; API 422 |
| PBF -1/101; visceral -1/101 | API 422; không chuyển thành 1 hoặc fallback số cũ |
| Context lưu 72kg nhưng text nhập -72kg | API 422; không dùng 72kg đã lưu |
| Thiếu cân nặng hoặc chiều cao | Hỏi bổ sung; không dựng mặc định |
| Muốn giảm 2kg; khoảng cân nặng; nhiều số đo không rõ thời điểm | Không tự chọn thành số đo hiện tại để tính |
| Đau ngực + khó thở + -72kg | Urgent 200; DB/queue/LLM/retrieval không được gọi |
| Chat async với số sai | 422 trước create_task/apply_async; không tạo transcript |

Chặn DB/queue/provider bằng mock gây lỗi để chứng minh thứ tự, đồng thời kiểm tra status/result chứ không chỉ spy call count.

## 4. FIX-02 — Routing lời chào và giữ đúng safety

### Files và thay đổi

- `backend/src/agents/fast_paths.py`: `_try_general_fast_path`, `_try_inbody_fast_path`.
- `backend/src/agents/graph.py`: thứ tự precheck/fast-path; `nodes/supervisor.py`, `nodes/safety.py` chỉ sửa nếu cần để giữ invariant.
- `backend/src/agents/composer.py`: kiểm tra các nhánh return sớm có giữ cảnh báo; tránh đụng logic citation/cache ngoài phạm vi.
- Tests: `test_agent_fast_paths.py`, `test_safety_and_evidence.py`, `test_three_specialist_agents.py`, integration fast paths.

1. Greeting fast path chỉ nhận lời chào/cảm ơn/giới thiệu khả năng thuần. Dùng deterministic matcher có kiểm soát, không gọi LLM chỉ để phân biệt lời chào.
2. `Xin chào, tính BMI 72kg 170cm` phải qua InBody; câu về thuốc/bệnh phải qua medical caution. Không xóa tiền tố rồi làm mất câu hỏi gốc trong response/logical context.
3. Giữ thiết kế caution hiện có: khi medical_caution, bỏ general/InBody template fast path và đi route safety retrieval; không sinh nutrition/training plan hoặc web advice. Như vậy không mở ngoại lệ tool-only mới cho bệnh nền trong đợt hotfix.
4. Mọi trace lấy risk thật từ safety_result, không ghi cứng low. Các nhánh thiếu evidence hoặc lỗi provider vẫn phải giữ lời cảnh báo theo recommended_action. Nếu cần fallback, dùng template tiếng Việt có giới hạn, không dựng citation.
5. Urgent luôn đứng trước normalize/router/RAG/LLM/DB; greeting thuần và BMI low-risk đủ dữ liệu giữ zero LLM/search.

### Test bắt buộc

- Greeting thuần cũ vẫn trả ngay; greeting + BMI hợp lệ tính 24.91; cảm ơn + câu hỏi dinh dưỡng không bị nuốt.
- Greeting + liều thuốc/bệnh nền: medical_caution, không general_chat, không lifestyle/web; trace và safety_result đồng nhất.
- Caution + BMI: không chạy template low-risk; không đưa kế hoạch tự động. Evidence rỗng/provider lỗi vẫn có hướng dẫn thận trọng.
- Greeting + urgent, urgent + invalid input và urgent + context bệnh nền: zero DB/LLM/search/queue; không làm mất hướng dẫn cấp cứu.
- Các định danh selected_agents chỉ thuộc ba specialist công khai; urgent có thể rỗng như contract hiện tại.

## 5. FIX-03 — Nâng dependency frontend có kiểm soát

### Files

`frontend/package.json`, `frontend/package-lock.json`; chỉ chỉnh `frontend/next.config.ts` hoặc code component khi hướng dẫn phiên bản/lỗi test thực sự yêu cầu.

1. Đọc `frontend/AGENTS.md` và docs đi kèm Next đang cài. Xác minh advisory/phiên bản tại lúc triển khai; theo kết quả 17/11, Next 16.4.3 bị GHSA-mfr8-8qww-v76h, vá từ 16.4.5, npm đề xuất 16.4.6.
2. Chọn patch đã vá tương thích trong nhánh 16.4; pin `next` và `eslint-config-next` cùng phiên bản. Chỉ đổi React nếu peer dependency yêu cầu. Cập nhật lockfile bằng npm, kiểm tra thay đổi dependency bắc cầu.
3. Xử lý minimatch/typescript-eslint moderate bằng bản cập nhật tương thích của owner dependency; không tự ép override major hoặc dùng `npm audit fix --force`.
4. Nghiệm thu `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npm run build` đều exit 0; audit không còn advisory Next/minimatch đang xử lý. Nếu advisory khác còn tồn tại, liệt kê package, runtime/dev scope, tác động và lý do chưa sửa.
5. Build bị chặn dù prerender xong vẫn là fail. Không tắt kiểm tra bảo mật để ghi pass.

Tham khảo: https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h

## 6. FIX-04 — Đồng bộ browser, auth và network triển khai

### 6.1 Frontend API URL (F3)

- Files: `frontend/Dockerfile`, `frontend/docker-compose.yml`, `frontend/.env.example`; `frontend/src/lib/api.ts` chỉ sửa nếu lỗi URL thực sự cần; thêm `frontend/.dockerignore`.
- Chọn giải pháp nhỏ: public URL và AUTH_MODE được cấp bằng build args → ARG/ENV ở builder trước npm run build. Compose không đặt runtime NEXT_PUBLIC_API_URL như thể nó có thể sửa bundle.
- Dùng URL browser truy cập được: local `http://localhost:8000`; máy khác dùng hostname/IP/domain backend thật. Không đặt `chatbot-api` làm public URL. Việc đổi URL/mode phải rebuild UI.
- Production build mặc định auth production; development phải chọn tường minh và khớp backend. Không truyền signing key/API key/biến backend vào build args công khai.
- `.dockerignore` loại node_modules, .next, .git, log và .env* riêng tư; giữ template cần thiết. Điều này tránh build vô tình đóng gói cấu hình dev hoặc output host.
- Nghiệm thu hai build với hai URL tổng hợp khác nhau; xác nhận bundle dùng URL build đã chọn. Sau đó kiểm browser trên máy khác khi có môi trường; local cùng host không đủ chứng minh đường LAN.
- Tham khảo: https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser

### 6.2 Auth/CORS và cách khởi chạy (F4)

- Files: `backend/.env.example`, `frontend/.env.example`, `SETUP.md`, `backend/README.md`; `backend/docker-compose.yml` nếu cần truyền config tường minh.
- Giữ production fail closed khi thiếu signing key/issuer/audience. Hướng dẫn tạo secret ngẫu nhiên tối thiểu 32 byte tại máy, không in/ghi secret vào report hoặc Git; issuer/audience là cấu hình first-party, không cần IdP ngoài.
- Hướng dẫn `CORS_ALLOWED_ORIGINS` bằng origin frontend thực tế (scheme/host/port, không path); ví dụ local localhost và 127.0.0.1. Tránh wildcard và tránh tự bật development để vượt lỗi auth.
- Lệnh Compose dùng `--env-file backend/.env` hoặc `frontend/.env` rõ ràng, vì biến nội suy Compose và service env_file là hai giai đoạn khác nhau. Kiểm tra AUTH_MODE/LLM_PROVIDER/DATABASE_URL có bị default environment ghi đè `.env` hay không; không in kết quả compose config đầy secret vào bằng chứng.
- SETUP cập nhật ba specialist/workflow stage thật; lệnh syntax dùng `api/app.py`, `agents/graph.py`, `llm/client.py`, `jobs/tasks.py` thay file legacy đã mất. Cập nhật hướng dẫn AGENTS tương ứng nếu nằm trong đợt được giao.
- Tests trong `test_first_party_auth.py`/`test_api_boundaries_wp03.py`: allowed origin preflight đạt; origin lạ bị chặn; production dev-header/forged/expired token bị từ chối; owner B không đọc dữ liệu A. Không nới middleware chỉ để test pass.

### 6.3 Giới hạn exposure infra (F6)

- Files: `infra/docker-compose.infra.yml`, tài liệu môi trường infra và `SETUP.md`; inventory script dùng host port trước khi đổi.
- Mặc định local: bind PostgreSQL/Qdrant/Valkey và embedding host port về 127.0.0.1. Container vẫn giao tiếp qua service DNS/internal-network; không dùng localhost bên trong container để gọi nhau.
- Bỏ fallback mật khẩu Postgres cố định; biến bắt buộc lấy từ file local không track. Thay cấu hình secret không tự đổi password role trong volume cũ: phải kiểm tra credential hiện tại và có bước rotation riêng nếu cần, không reset volume.
- Không xoay password/xóa volume/thêm auth Qdrant hoặc Valkey vào runtime hiện hữu mà chưa inventory toàn bộ client. Shared deployment cần lát cắt auth/network riêng qua API/worker/scheduler/import/monitoring; bản local bind không được báo là nghiệm thu shared production.
- Nghiệm thu Compose config với env test tổng hợp; runtime inspect port binding; Postgres SELECT 1, Valkey ping, Qdrant read-only health/count; kết nối API/worker vẫn đạt. Không dùng config hợp lệ để thay cho kiểm tra kết nối.

## 7. FIX-05 — Nghiệm thu runtime và rollback

### Preflight bắt buộc

- Ghi revision + diff được triển khai, phiên bản Python/Node/image, profile/env không có secret.
- Ghi Qdrant collection/alias/status/count, corpus/manifest version, process/job import và log cuối; xác định job bulk import có đang chạy.
- Nếu không truy cập được daemon hoặc job import chưa rõ: dừng bước deploy, giữ SOURCE_READY/NOT_RUN. Không chạy `down -v`, không xóa collection, không swap alias trong hotfix này.
- Ưu tiên stack test biệt lập có network/port/volume riêng và dữ liệu tổng hợp. Chỉ cập nhật stack hiện hữu khi phạm vi triển khai đã được cho phép và preflight đạt; không chạy migration/seed vào DB thật để làm smoke test.

### Bộ kiểm tra qua HTTP thật và browser

| Nhóm | Ca bắt buộc | Gate |
|---|---|---|
| Health | /health, /health/ready | Readiness phản ánh dependency; không coi healthy liveness là mọi dịch vụ sẵn sàng |
| Auth | Register/login, invalid/expired token, dev header ở production | Đúng 201/200/401; thiếu config/dependency fail closed |
| UI | Login → consent → profile → số đo → chat có conversation_id → logout/login user B | Dữ liệu thật, lỗi thật; không dữ liệu A ở B; không cần reload để cập nhật trạng thái auth |
| Fast path | Greeting thuần, BMI 72/170, greeting+BMI, urgent kể cả số sai | Kết quả đúng; urgent/BMI low-risk không gọi provider/search |
| Invalid | Chat số âm/ngoài miền, /tools/bmi âm | HTTP 422; không task/transcript/kết quả số đo giả |
| Caution | Liều thuốc/bệnh nền + lời chào/BMI; provider hoặc evidence vắng | Giữ cảnh báo; không tự lập kế hoạch; trace risk đúng |
| RAG | InBody, nutrition, exercise, safety retrieval | Context thật/citation hợp lệ hoặc limitation rõ; safety không recipe |
| Error | Backend offline, storage unavailable, auth hết hạn, request timeout | UI không đổi sang mock/success; status lỗi/degraded đúng contract |

- Đo tối thiểu 100 request mỗi fast path sau warm-up; lưu mẫu latency, concurrency, hardware và config. Gate P95 urgent và BMI low-risk < 500ms theo AGENTS; ghi riêng ảnh hưởng auth/HTTP và dependency. Request chuẩn không vượt 60s; frontend timeout phải lớn hơn backend hard timeout.
- TestClient, fixture và LLM_PROVIDER=none không chứng minh chất lượng provider/RAG. Provider có phí cần xác định quyền và ngân sách trước khi chạy; dữ liệu eval chỉ dùng tổng hợp hoặc đã được cho phép.
- Nếu chưa có corpus/version hoặc provider cấu hình, đánh dấu RAG/provider NOT_RUN; chưa đóng toàn bộ FIX-05. Benchmark Recall@5/citation precision/soak là gate riêng cho RAG beta, không suy ra từ vài smoke case.

### Rollback

- Lưu image tag/config cũ trước deploy. Khi startup/readiness/smoke fail: dừng rollout và khôi phục image/config trước, không sửa dữ liệu/alias để che lỗi.
- Source rollback bằng patch hoặc commit reversal đã xác định phạm vi, không reset working tree và không xóa thay đổi khác. Các đợt này không yêu cầu schema migration.

## 8. Hồ sơ nghiệm thu và bàn giao

Mỗi đợt ghi vào `docs/reports/upgrade-2026/` tên finding, reproduction trước/sau, file sửa, lệnh và exit code, số test, môi trường, runtime revision, phần NOT_RUN và rollback nếu có. Cập nhật mục tiến độ trong `docs/KE_HOACH_NANG_CAP_DU_AN_2026.md`, dẫn báo cáo mới; không ghi đè bằng chứng lịch sử.

| Đợt | Source | Test | Runtime |
|---|---|---|---|
| FIX-01 | SOURCE_READY | 217 unit + 3 API integration đạt | 8/8 HTTP biệt lập đạt; chưa deploy container/PostgreSQL |
| FIX-02 | SOURCE_READY | 250 unit + 3 integration đạt; 33 regression mới | 9/9 HTTP fast-path biệt lập đạt; health timeout, caution/Qdrant/provider thật NOT_RUN |
| FIX-03 | SOURCE_READY | npm ci/lint/tsc/build exit 0; audit 0 vulnerabilities | 5/5 HTTP production-build host checks đạt; chưa image/browser E2E |
| FIX-04 | SOURCE_READY | 264 unit + 3 integration đạt; Compose env/binding/password, 2 build sentinel + khôi phục, lint/tsc đạt | 8/8 HTTP CORS/JWT/bundle checks host đạt; Docker image/binding/dependency thật NOT_RUN |
| FIX-05 | Chờ FIX-01–04 | Chờ môi trường | Docker chưa sẵn sàng |

## 9. Chỉ dẫn bắt đầu cho coding agent

Đọc AGENTS.md, báo cáo rà soát, báo cáo FIX-01–04 và tài liệu này; kiểm tra git status/diff. FIX-01–04 đã sửa và kiểm chứng theo phạm vi từng báo cáo, không làm lại nếu chưa có regression mới. Đợt tiếp theo là FIX-05 khi được giao triển khai và Engine/preflight sẵn sàng. Tiếp tục lần lượt theo gate; không đổi graph architecture, không mở Zep, không làm migration corpus hay commit/push ngoài yêu cầu. Mọi tuyên bố hoàn thành phải phân biệt source, test trong process, HTTP runtime và browser.

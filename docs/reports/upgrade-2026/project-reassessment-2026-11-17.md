# Đánh giá lại toàn dự án — 17/11/2026

## Kết luận

Dự án đã có nền tảng MVP tương đối đầy đủ và có thể tiếp tục phát triển trên kiến trúc hiện tại. Tuy nhiên, **chưa đủ điều kiện nghiệm thu RAG beta hoặc production candidate**. Những vấn đề đáng ưu tiên hiện nằm ở độ đúng của dữ liệu và bằng chứng, an toàn giữa các màn hình, và tính nhất quán khi chạy tích hợp; tăng số agent hay đổi framework chưa giải quyết các vấn đề này.

Đánh giá này tìm được **13 nhóm vấn đề cần xử lý**, gồm lỗi tái hiện trong process và khoảng trống xác minh được từ source. Không tìm thấy bằng chứng để kết luận đã xảy ra rò rỉ dữ liệu giữa người dùng, mất dữ liệu Qdrant hoặc sự cố y khoa ngoài thực tế. Các tình huống bất lợi dưới đây dùng dữ liệu tổng hợp, mock và dịch vụ bị thay thế trong process.

- Revision: `5c8124cc3a8d61c9dd0d821641ed2c9796a94cc5`, nhánh `main`.
- Trước đánh giá, chỉ `README.md` có thay đổi chưa commit. Giữ nguyên thay đổi đó.
- Chỉ thêm báo cáo này và [bằng chứng JSON](project-reassessment-2026-11-17-evidence.json). Không sửa source, dependency, dữ liệu, cấu hình riêng, migration; không restart/deploy/stage/commit/push.
- Docker Engine trả lỗi truy cập API; các GET localhost đến API/UI/Qdrant/embedding/OCR đều timeout. Đây là giới hạn truy cập trong lượt này, không phải bằng chứng dữ liệu hoặc volume đã mất.

## Kiến trúc và luồng thực tế

Frontend Next.js gọi FastAPI bằng browser API URL. `/agent/answer` và `/chat/complete` xác thực danh tính rồi dùng chung `memory.chat.run_chat`. Nhánh urgent được kiểm tra trước DB/history/queue; các request còn lại được xác thực số đo, nạp context có consent và lịch sử thuộc owner, rồi gọi graph. Kết quả có thể được ghi thành lượt chat và đề xuất memory.

Graph hiện có ba specialist công khai: **InBodyAgent, LifestyleAgent, KnowledgeAgent**. Ba node chạy nối tiếp; capability bên trong tự bỏ qua khi không được chọn. Đây không phải ba mô hình độc lập hoặc ba LLM chạy song song. Safety, normalize, router, context và composer là các bước điều phối. PostgreSQL giữ dữ liệu cá nhân; Qdrant và BM25 phục vụ corpus chung. Celery dùng cùng đường chat và có lịch purge memory. OCR là dịch vụ riêng, PaddleOCR → định dạng layout → text LLM → validation → người dùng xác nhận → API lưu số đo.

Có hai đường nhập corpus: importer trong backend và pipeline `data_pipeline/`. Các đường này chưa có cùng mức bảo vệ với API quản trị staging. `contracts/` còn mô tả Core/Agent service split, nhưng không được import trong luồng backend đang chạy; không coi các schema này là hợp đồng thực thi của UI hiện tại.

## Phạm vi đã khảo sát

| Phân hệ/use case | Độ sâu khảo sát | Bằng chứng và giới hạn |
|---|---|---|
| Entrypoint, cấu hình, Compose, auth | Đọc entrypoint, dependency, issuer/subject, account flow, deployment files | Source, unit, Compose render; chưa có runtime production |
| Chat sync/async, ownership, memory | Lần API → run_chat → context/history → graph → record_turn; đọc task/retention/consent | Unit và TestClient; không kiểm chứng transaction/lock PostgreSQL thật |
| Routing, fast paths, safety | Đọc graph, specialist, parser/validation, router và capability chính | Regression hiện có đạt; chưa có accuracy/HTTP P95 đại diện |
| Composer, citation, injection, budget/cache | Đọc producer/consumer và guard; probe đảo nghĩa, timeout | Tái hiện trong process với provider giả |
| Retrieval, Qdrant, BM25, rerank | Đọc search/filter/fusion/parent expansion, Qdrant writer/alias, reranker | Source, test, snapshot local; không truy cập Qdrant thật |
| Offline corpus/import | Đọc cả hai entrypoint, indexer, manifest, metadata; thống kê corpus local | Mock write; không ghi collection hoặc chạy embedding |
| Profile/goal/measurement/progress/plan/check-in | Đọc API/schema và service ownership/consent/version/provenance; đối chiếu adapter/UI | Unit và source; chưa nghiệm thu schema/volume thật |
| Frontend chat/dashboard/profile/search/OCR/auth | Đọc adapter và các consumer chính; chạy adapter TS bằng mock fetch | Lint/typecheck/build đạt; không phải browser E2E hoặc visual/accessibility audit |
| OCR service/gateway | Đọc upload → Paddle → LLM → validation → UI confirmation | 16 test; probe LLM bịa cả số và raw_text; chưa chạy model thật |
| Embedding/GPU | Đọc device/dtype/batch/health và Compose CPU/GPU | Source; chưa load BGE-M3, đo VRAM/throughput hoặc benchmark đồng thời LLM |
| Observability, backup/privacy lifecycle | Đọc helper Langfuse, scheduler, deployment và hướng dẫn DB | Source; chưa xác minh spans/retention/restore runtime |

Kiểm kê cú pháp bao phủ 87 file Python backend, 18 file pipeline (kể cả test), 18 file OCR source, 3 script embedding và 4 file contracts; frontend có 26 file TS/TSX. Đây là kiểm kê/cú pháp, **không có nghĩa đã review thủ công từng dòng**. Không đọc nội dung secret/env riêng, dependency/build/cache, trọng số model, toàn bộ dữ liệu thô 103 MB hoặc từng tài liệu y khoa.

## Kiểm tra đã thực thi

| Kiểm tra | Kết quả hiện tại |
|---|---|
| Backend unit + integration fast paths | **267 passed**, 2 cảnh báo `on_event`; Python host 3.13.2, không phải image Python 3.10 |
| Pipeline tests + Zep SDK contract suite | **10 passed, 1 skipped**; Zep SDK suite bị skip vì dependency không có trên host |
| OCR tests | **16 passed**; Paddle/LLM giả trong các ca liên quan, không phải accuracy OCR thật |
| Frontend ESLint và TypeScript | Cả hai exit 0 |
| Frontend production build | Exit 0; Next.js 16.4.6, compile/typecheck/prerender đạt |
| npm audit | 0 advisory được registry báo tại thời điểm chạy; không phải chứng nhận bảo mật ứng dụng |
| Python syntax + grammar 3.10 | 130 file không có lỗi; không chứng minh dependency/runtime image tương thích |
| Compose infra/backend/embedding/OCR | `config --quiet` exit 0 từng lệnh |
| Compose frontend | File `frontend/.env` không tồn tại → lệnh dùng file đó exit 1; dùng `.env.example` thì config exit 0 |
| Eval Phase 1 trên snapshot local hiện tại | Preflight dừng: `fixture corpus_version does not match snapshot`; chưa sinh metric mới |
| HTTP runtime và Docker | Chưa truy cập được; không có HTTP smoke test tích hợp đạt trong lượt này |
| Whitespace diff | `README.md:255` có blank line tại EOF từ thay đổi có sẵn; không tự sửa |

Các lệnh chính: `python -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider`; `python -m pytest data_pipeline/tests backend/tests/integration/test_zep_sdk_contract.py -q -p no:cacheprovider`; `python -m pytest ocr-paddle-services/tests -q -p no:cacheprovider`; `npm run lint`; `npx tsc --noEmit`; `npm run build`. `PYTHONPATH` được chọn riêng cho backend/OCR.

## Những phần đang làm đúng

- Các lỗi số đo âm và lời chào lấn át yêu cầu trong báo cáo trước đã có thay đổi source và regression xanh. Không tiếp tục liệt kê chúng như lỗi còn nguyên.
- JWT kiểm chữ ký/algorithm/issuer/audience/time claims; production không nhận dev identity. Password dùng Argon2id; login/register có limiter dùng Valkey và fail closed khi limiter không sẵn sàng.
- Service cá nhân hóa lọc owner, consent; context chỉ lấy số đo đã xác nhận và chưa xóa. Memory facts phải gắn lời user và được xác nhận, không tự trở thành evidence y khoa.
- Urgent có deterministic bypass trước các dependency trong đường chat; greeting thuần/BMI low-risk có fast path. Test chứng minh bypass bằng mock gây lỗi ở dependency.
- Medical caution hạn chế route sang safety retrieval; filter `medical_safety` áp dụng cả BM25 lẫn dense. Query gốc đứng đầu danh sách retrieval, mặc định một query.
- Importer backend có ID ổn định, content hash, manifest và nhánh writer fail-fast; có công cụ alias blue/green riêng. Vấn đề còn lại là việc bắt buộc sử dụng cơ chế đó trên mọi entrypoint.
- UI chỉ bật mock khi người dùng chọn demo trong development. Production JWT nằm trong RAM; Dev Tools bị chặn khỏi production UI.
- Embedding source chọn device/dtype tường minh và chặn FP16 trên CPU; không mặc định coi GPU 4 GB đủ cho tất cả model.

## Phát hiện ưu tiên

P1: ảnh hưởng độ đúng/an toàn, tính sẵn sàng hoặc invariant dữ liệu của chức năng chính, nên sửa trước nghiệm thu. P2: hỏng một luồng phụ, hợp đồng hiển thị hoặc thiếu bằng chứng/quản trị cần khép kín. Mức độ không phải xác nhận exploit hoặc sự cố production.

| ID | Mức | Vấn đề | Bằng chứng |
|---|---|---|---|
| R01 | P1 | Guard citation chấp nhận câu đảo nghĩa nguồn | Probe guard và composer |
| R02 | P1 | Budget timeout không đến OpenAI/custom provider | Probe adapter, source fallback/rerank |
| R03 | P1 | Network call đồng bộ trong async endpoint chặn event loop | Probe timer và route HTTP trong process |
| R04 | P1 | Dashboard đổi số đo thiếu thành 0, dùng PBF nam cho mọi người | Probe adapter + source consumer |
| R05 | P1 | Check-in làm mất cảnh báo urgent từ backend | Probe adapter + source UI |
| R06 | P1 | CLI importer vẫn ghi được vào tên collection đang phục vụ | Mock importer; source cả hai pipeline |
| R07 | P1 | Seed được tự đóng dấu guideline/medical approved bằng code | Source metadata producer |
| R08 | P2 | DNS OCR trong backend Compose không khớp service OCR | Đối chiếu hai Compose; chưa runtime |
| R09 | P2 | OCR chỉ so số với raw_text cùng do LLM sinh | Probe extractor |
| R10 | P2 | UI bỏ dữ liệu check-in/memory và nuốt lỗi hết phiên | Probe response mapping |
| R11 | P2 | Nội dung citation backend không đến thẻ citation UI | Probe adapter + component |
| R12 | P2 | API indexing báo thành công khi writer trả lỗi | Probe handler/task giả |
| R13 | P2 | Eval, version corpus và BM25 chưa có gate đồng bộ | Thống kê artifact + eval preflight/source |

### R01 — Citation hợp lệ về ID chưa bảo đảm đúng ý

Nguồn: `backend/src/harness/guards.py:55–94`, `agents/composer.py:424–440`. Guard dùng overlap từ, số và một kiểm tra phủ định theo một chiều. Nó chặn việc thêm “không” khi nguồn không có, nhưng không chặn việc bỏ “không” khỏi câu nguồn.

Probe tổng hợp: nguồn có câu “BMI không đủ để chẩn đoán sức khỏe.”; câu trả lời cố ý sai bỏ chữ “không”, gắn `[1]`. Guard chấp nhận; composer giữ nguyên câu sai, `evidence_status=supported` và tạo một claim/evidence link. Đây là kiểm tra logic, không phải lời tư vấn hoặc kết quả LLM thật.

Tác động: hệ thống có thể trình bày claim trái ý nguồn dưới nhãn supported. Owner sửa là guard/composer; cần regression đảo phủ định hai chiều, thay đổi điều kiện/đối tượng, câu có số giống nhau nhưng nghĩa khác. Không nâng lexical overlap thành bảo đảm entailment hoặc citation precision ≥95%; cần đánh giá trên claim được con người review.

### R02 — Timeout graph là ngân sách hợp tác, chưa phải hard timeout

Nguồn: `backend/src/llm/client.py:109–116,178–221,245–280`; `agents/context.py:62`; `rag/rerank.py:174`; `agents/nodes/web_search.py:27`. Hàm chung nhận `timeout`, nhưng OpenAI branch không truyền nó vào client/request; custom branch dùng `LLM_TIMEOUT` chung. Fallback sang OpenAI cũng thiếu deadline còn lại. Reranker ngoài không nhận budget từ state.

Probe yêu cầu timeout 0,01 giây: OpenAI SDK request không nhận trường timeout; HTTP custom nhận 60 giây. Không đo request provider thật kéo dài 60 giây và không suy ra con số latency production từ probe này. Graph chỉ kiểm thời gian trước/sau các bước; `run_in_threadpool` không tự ngắt hàm đồng bộ đang chờ I/O.

Cần truyền deadline còn lại qua mọi adapter, tính cả retry/fallback/normalize/router/rerank/web; kiểm thử transport trì hoãn và deadline tổng ở HTTP. Tham chiếu cách cấu hình timeout/retry của [SDK OpenAI](https://github.com/openai/openai-python#timeouts). Không coi timeout 65 giây của browser là hard timeout 60 giây của server.

### R03 — API tốn thời gian có thể trì hoãn request urgent khác

Nguồn: `backend/src/api/app.py:235–241,475–478,513–527,561–564`. `/search`, `/summarize` và indexing được khai báo `async def` nhưng gọi trực tiếp hàm đồng bộ có I/O; `/health` cũng gọi cache probe đồng bộ. Đường chat đã offload nhưng vẫn dùng chung event loop của Uvicorn worker với các endpoint này.

Probe thay search bằng hàm chờ 200 ms: callback timer 10 ms chỉ chạy sau 200,95 ms. Đây là event-loop test trong process, không phải HTTP P95. TestClient production không Authorization vẫn nhận 200 ở `/search` và `/summarize` khi provider giả, trong khi `/agent/answer` trả 401. Limiter tìm thấy chỉ nằm ở login/register; `SummaryRequest.text` cũng chưa có max length.

Tác động khi có tải: request tìm kiếm/tóm tắt có thể giữ worker và trì hoãn cả việc nhận request urgent, dù urgent tự nó không gọi RAG. Cần offload hoặc async I/O phù hợp, giới hạn kích thước/concurrency và policy truy cập cho API tốn tài nguyên. Test đồng thời search chậm + urgent nhanh trên HTTP thật. [FastAPI giải thích cách xử lý hàm đồng bộ và async](https://fastapi.tiangolo.com/async/).

### R04 — Giá trị chưa có bị biến thành chỉ số thực

Nguồn: `frontend/src/lib/api.ts:404–418`, `components/inbody/InBodyDashboard.tsx:143`. Các trường optional chỉ kiểm `!== undefined`; JSON `null` đi qua `Number(null)` thành 0. Probe SMM/BFM/PBF/visceral `null` đều nhận 0. Phân loại visceral của UI coi 0 là mức an toàn, nên dữ liệu thiếu có thể hiện như một đánh giá đã có số đo.

Dashboard còn gọi `classifyPbf(latestPbf, 'male')` cố định, dù profile có `sex_at_birth`. Danh sách số đo hợp lệ chỉ có metric khác mà thiếu weight/height cũng bị adapter loại hoàn toàn, trong khi schema backend cho phép lưu từng phần.

Cần chuẩn hóa `null/undefined/nonfinite` thành missing; giữ record từng phần và trạng thái chưa đủ dữ liệu; truyền giới tính từ hồ sơ, giữ unknown nếu không có. Regression phải kiểm output KPI/chart với missing/0/giá trị thật và profile khác nhau; không chỉ kiểm TypeScript.

### R05 — Cảnh báo triệu chứng trong check-in bị bỏ rơi

Nguồn: `persistence/personalization_service.py:860–899` trả `safety_result`; `frontend/src/lib/api.ts:746–757` không giữ trường đó; `components/profile/ProfileAndGoals.tsx:163–181,488` chỉ thêm log và thông báo lưu thành công.

Probe backend giả trả `risk_level=urgent` và hành động an toàn; kết quả `saveCheckIn` không còn `safety_result`. Không có consumer tương ứng để hiện cảnh báo như màn chat. Đây là lỗi hợp đồng/an toàn giữa màn hình, không chứng minh urgent fast path của chat hỏng.

Cần đưa safety_result qua type/adapter, hiển thị hành động ưu tiên ngay trong flow check-in, và thêm ca người dùng nhập triệu chứng → thấy cảnh báo, kể cả khi lưu log thành công. Form còn thu sleep_hours/workout_rating nhưng payload lưu sleep_quality/soreness theo mặc định; phải thống nhất ý nghĩa và không thay dữ liệu nhập bằng các chỉ số khác.

### R06 — Quy tắc staging chưa bảo vệ đường CLI

Nguồn: `backend/src/pipelines/import_data.py:443–498,616,661`; `data_pipeline/configs/pipeline_config.py:59`; `data_pipeline/run_pipeline.py:281–340`; `rag/corpus_policy.py:48`. API quản trị gọi `require_staging_collection`; importer CLI không dùng guard này và mặc định nhận `nmk_chatbot_active`. Pipeline riêng cũng ghi vào tên mặc định đó.

Probe với toàn bộ embedding/writer/Qdrant bị mock: gọi importer không truyền collection vẫn dispatch write tới `nmk_chatbot_active` và trả status true. **Không có write thật.** Nếu đây là serving alias/collection trong môi trường triển khai, stable IDs có thể cập nhật trực tiếp corpus đang phục vụ và tạo pha trộn phiên bản.

Cần một admission policy dùng chung, bắt buộc physical staging collection/version trước khi tạo/ghi, kiểm actual alias target, manifest và dry-run trước activation. Test phải chứng minh serving alias lẫn physical target bị từ chối trước embedding/upsert. Giữ công cụ blue/green hiện có; không cần đổi vector DB.

### R07 — Nhãn review đang được sinh như metadata mặc định

Nguồn: `data_pipeline/src/processors/corpus_processor.py:458–479`. `seed_document` tự ghi `source_tier=guideline`, `medical_review_status=approved`, ngày publish/review cố định và publisher mặc định cho seed. Một số source_url trong seed còn là `internal_curated`. Không có bằng chứng trong luồng này rằng người có chuyên môn đã review nội dung hoặc những ngày đó là ngày thật của tài liệu.

Kiểm tra artifact local 1.009 document: mỗi trường source_url/publisher/source_tier/published_at/reviewed_at/medical_review_status chỉ có mặt ở 56 record. Số trường có mặt **không chứng minh nguồn hợp lệ hoặc đã review**. Corpus gồm 558 nutrition, 404 exercise, 35 inbody, 11 medical_safety, 1 general_health; phân bố mất cân đối cần được xét theo use case, không dùng số lượng tài liệu thay cho coverage safety.

Cần giữ trạng thái unreviewed/provisional nếu chưa có record review thật; lưu reviewer, đối tượng/phiên bản được review, ngày và tài liệu gốc. Không tự gán guideline/approved để qua validator. Lấy mẫu chuyên môn và xây eval theo từng chủ đề, đặc biệt safety; không kết luận accuracy từ việc schema is_valid.

### R08 — Hai Compose không thống nhất tên dịch vụ OCR

Nguồn: `backend/docker-compose.yml:36` ép `OCR_SERVICE_URL=http://ocr-api:18100`; `ocr-paddle-services/compose.yaml:2` đặt service `ocr-paddle-api`, không có network alias `ocr-api`. `environment` tường minh còn ghi đè `env_file`.

Khi bật FEATURE_OCR_UPLOAD và dùng đúng hai Compose hiện tại, source cấu hình không cung cấp DNS đích mà gateway gọi. Chưa xác minh Docker DNS runtime; một dịch vụ/alias ngoài repo có thể thay đổi kết quả thực tế.

Cần thống nhất service name/alias hoặc cấu hình URL có nội suy; sau đó test upload qua gateway thật. Service OCR hiện publish `18100:18100` và không có auth riêng, nên deployment chia sẻ cũng cần quyết định đường truy cập nội bộ/bảo vệ cổng này.

### R09 — OCR chưa nối validation với kết quả Paddle

Nguồn: `ocr-paddle-services/src/inbody_ocr/inbody/extractor.py:60–79,100–127`. `plain_text` được gửi vào LLM, nhưng `_validated_field` chỉ nhận item do LLM sinh và so `value` với `raw_text` trong chính item đó.

Probe Paddle chỉ thấy `72.5 kg`; LLM giả trả cả value 82.5 và raw_text `82.5 kg`. Extractor vẫn chấp nhận weight, không warning. Test hiện có mới bắt tình huống value bịa nhưng raw_text còn đúng.

Luồng vẫn trả `needs_confirmation`, UI vẫn yêu cầu đối chiếu/lưu; do đó chưa phải auto-save dữ liệu sai. Cần kiểm raw_text/page/label against OCR lines hoặc span/box có provenance, thêm ca cả value và raw_text cùng bịa, nhầm cột và nhầm đơn vị. Accuracy phải đo bằng ảnh có nhãn, không dùng 16 unit test thay thế.

### R10 — Backend có dữ liệu nhưng UI trả danh sách rỗng

Nguồn: `api/personalization.py` GET `/check-ins` và `memory/store.py:128–138` trả `{items: [...]}`. Adapter `frontend/src/lib/api.ts:680,788` đọc `check_ins` hoặc `facts`. Với mỗi response có một item tổng hợp, hai adapter đều trả 0 item. Người dùng có thể nghĩ lịch sử/ghi nhớ đã mất dù backend còn dữ liệu.

Các nhánh `api.ts:702,805` còn chuyển 401/403 thành `[]`, bỏ qua `ApiError` vốn phát sự kiện auth-expired. Probe sau khi đặt token: memory endpoint trả 401, adapter vẫn trả [] và giữ token.

Cần mapper theo response thực thi, phân biệt empty/error/consent/auth expiry và hiển thị trạng thái đúng. Test producer → adapter → consumer với `{items}`, consent 409, 401/403 và response lỗi; không dựa vào fixture hình dạng cũ.

### R11 — Người dùng chưa xem được đoạn evidence từ câu trả lời

Nguồn: `harness/layers/citation_checker.py:14–38` xuất `excerpt`, `retrieval_score`; `frontend/src/lib/api.ts:224` giữ nguyên object; `components/chat/CitationsView.tsx:40–42,82` đọc `score`, `content`. Probe response thật về cấu trúc cho thấy excerpt có dữ liệu nhưng content/score của UI là missing. Thẻ có thể có title/source mà đoạn trích mở ra rỗng.

Cần một contract/mapping dùng chung và kiểm card render với API response. Giữ document_id/chunk_id/source_url/version để truy vết; không đánh đồng score với độ đúng y khoa. Lint/typecheck xanh không phát hiện lỗi này vì JSON đang là dữ liệu không được validate ở boundary.

### R12 — Đường indexing API không fail-fast như importer

Nguồn: `jobs/tasks.py:119–164`; `rag/qdrant/client.py:104–168`; `api/app.py:513–517`. `add_vector` mặc định gom lỗi thành result; `index_document_v2` không bật raise_on_error, `index_health_documents` đếm số lần thử là indexed và handler bọc `status=true`.

Probe writer giả trả lỗi một batch: handler vẫn trả status true, indexed 1, còn lỗi nằm sâu trong statuses. Đây là handler/task probe; chưa gây lỗi Qdrant thật. Đường CLI có `add_vector_safe(...raise_on_error=True)` nên đã có cơ chế có thể tái sử dụng.

Cần contract failure/partial rõ ràng, thành công tính theo receipt thực, trả 502/503 phù hợp hoặc tác vụ thất bại có chủ đích. Regression dùng writer lỗi và kiểm HTTP/result bên consumer, manifest không được tuyên bố import hoàn tất.

### R13 — Chưa có chất lượng RAG đo trên corpus đang dùng

Snapshot local đang có **4.405 chunk, 4.405 doc_id duy nhất, version `2026.1`**. Fixture Phase 1 pin `2026-07-30-v2`; chạy preflight hiện dừng vì version mismatch. Báo cáo baseline cũ dùng snapshot 23.608 document và model none. Không được chuyển những metric đó sang corpus hiện tại. Cũng không sửa version fixture đơn thuần để “chạy xanh”.

Ngoài version, fixture routing cũ so các capability RAGAgent/NutritionAgent/TrainingAgent với selected_agents, trong khi contract công khai hiện có ba specialist. Cần cập nhật expected theo đúng lớp đang đánh giá, giữ holdout độc lập và review relevance labels.

`rag/search.py:284–310` kiểm tên collection/schema/count khi load snapshot nhưng không đối chiếu actual alias target/version/hash Qdrant. Alias name ổn định có thể trỏ sang corpus mới trong khi BM25 vẫn là artifact cũ. `data_pipeline/run_pipeline.py:256,265` còn hard-code version `2026.1`. BM25 tiếp tục giữ `_documents`/`_bm25_index` trong mỗi process (`search.py:30–33`), nên snapshot gzip chưa đáp ứng quy tắc không giữ index riêng từng worker khi tăng API_WORKERS. Rerank vẫn tự chạy heuristic/Cohere khi có key; chưa có bằng chứng MRR/NDCG mới cho cấu hình này.

Cần gói release corpus gồm physical collection, alias target, source/chunk manifest, snapshot hash và eval fixture cùng version. Kiểm count/hash/ID và refuse/degrade mismatch; xử lý ownership của lexical index trước scale worker. Sau đó đo routing, dense/BM25/fusion/rerank riêng trên cùng corpus, Recall@5, strict top-1, Safety Hit@5, recipe leakage và citation precision theo rubric có người review.

## Các khoảng trống bổ sung

- **Plan evidence:** `create_plan` kiểm owner của measurement và khớp ID giữa evidence_ids/citations do client gửi, chưa resolve các ID đó về corpus/evidence của request đã lưu. Không nên coi active plan là kế hoạch đã được xác minh chỉ từ JSON này. Chưa thực hiện probe DB cho việc giả provenance.
- **Observability:** tìm caller trong backend/src chỉ thấy các định nghĩa Langfuse helpers; chưa thấy nối start_trace/trace_span/record_generation vào đường run_chat/graph/provider. Bật flag chưa chứng minh có trace hoặc token/cost runtime. Helper redaction cũng chưa phải lớp che toàn bộ prompt sức khỏe.
- **Auth/privacy:** chưa có revoke/refresh/password reset/account export-delete flow hoàn chỉnh. Subject từ JWT hợp lệ không được tra active/deleted account ở mọi request; chưa test thu hồi account/token thật. Đây là việc cần chốt theo phạm vi sản phẩm, không phải bằng chứng cross-user leak.
- **Infra:** main infra đã bind cổng dữ liệu loopback, nhưng monitoring Compose còn credential fallback cố định và port 3000 trùng frontend; Qdrant image dùng latest, dependency Python có nhiều dải mở. Chưa dựng image mới để kiểm độ tái lập hoặc audit dependency backend trong đúng image.
- **Dữ liệu và vận hành:** chưa xem migration ledger trên volume thật, kiểm backup/restore, Celery broker/result expiry/purge runtime, job import, alias/count/collection status hoặc corpus đầy đủ.
- **UX:** searchCorpusApi bỏ qua category ngoài demo; chọn nutrition và medical_safety sinh payload giống hệt nhau. Header có thể giữ số đo cuối sau khi xóa hết vì refresh không clear state khi response rỗng. Chuyển tab unmount ChatContainer, chưa có UI khôi phục lịch sử hội thoại. Chưa chạy browser/mobile/accessibility; đây là source observations, không phải nghiệm thu visual.
- **Tài liệu:** hai báo cáo bắt buộc đọc trong AGENTS (`docs/P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md`, `docs/P1_PERSONALIZATION_REPORT.md`) hiện không có tại đường dẫn đó. Roadmap còn nhiều mô tả cũ. Chưa sửa chúng trong lượt review. Fresh init.sql có auth_credentials nhưng ledger mới ghi P1/memory; cần thống nhất với migration auth khi hoàn thiện runbook.

## Đánh giá mức sẵn sàng

| Mục tiêu | Kết luận | Điều còn thiếu |
|---|---|---|
| Nền tảng source MVP | Đã có nhiều luồng thực, test đạt | Còn các lỗi đã tái hiện; không đồng nghĩa source hoàn chỉnh |
| Demo local có hướng dẫn | Có triển vọng, chưa nghiệm thu lượt này | Docker/API/dependency/browser thật và cấu hình frontend/OCR |
| Agent P0 | Chưa chứng minh đạt gate runtime | Urgent/tool-only HTTP P95, zero-call dưới tải, request deadline tổng |
| RAG beta | Chưa đủ bằng chứng | Corpus/eval đồng phiên bản, provenance thật, retrieval/citation metrics |
| Production candidate | Chưa đạt | R01–R13, auth/privacy/deploy/restore/soak/browser gates |

Không chấm điểm tổng kiểu “8/10” hoặc phần trăm hoàn thành: test, module, dữ liệu và runtime không cùng đơn vị; điểm tổng sẽ che những gate an toàn chưa đạt.

## Thứ tự xử lý đề nghị

1. **Khép kín độ đúng/an toàn:** R01, R04, R05 và R07; regression rõ ràng trước khi sửa. Cùng đợt frontend adapter sửa R10/R11 để người dùng nhìn được dữ liệu và bằng chứng thật.
2. **Khép kín giới hạn thực thi:** R02/R03; chứng minh concurrent urgent không bị search/summarize làm nghẽn, tính budget end-to-end cho mọi provider.
3. **Tách đợt dữ liệu riêng:** R06/R12/R13; staging guard, write receipts, provenance/manifest, chốt corpus và fixture. Không trộn thay corpus lớn với hotfix Agent.
4. **Nghiệm thu OCR:** R08/R09, ảnh có nhãn, gateway thật, confirm/save/readback; giữ confirmation bắt buộc.
5. **Nghiệm thu runtime trên cùng revision/config:** sau khi truy cập được Docker, ghi import jobs + alias/collection/status/count + manifest/log cuối trước bất kỳ restart; kiểm migration ledger/backup; deploy có kiểm soát và HTTP smoke theo AGENTS.
6. **Gate sản phẩm:** browser login → consent → profile → manual/OCR measurement → chat → citation → check-in warning → memory confirm/delete → owner isolation; benchmark RAG cùng corpus, P50/P95 và soak trên cấu hình GPU/CPU đã chọn.

Giữ backend gộp và ba specialist hiện tại trong các đợt này. Ưu tiên hợp đồng dữ liệu, bằng chứng và nghiệm thu thay vì thêm agent/service. Báo cáo này là đánh giá và đề nghị; **chưa triển khai các sửa đổi**.

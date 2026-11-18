# Rà soát độc lập sau sửa — 18/11/2026

## Kết luận và giới hạn snapshot

Chưa thể nghiệm thu Agent P0, RAG beta, OCR E2E hoặc production. Có cải thiện rõ ở frontend, deadline, staging và local memory, nhưng các probe độc lập vẫn tái hiện lỗi claim, provenance, trộn release, OCR và starvation của urgent. Không sửa source ứng dụng, không deploy, không ghi corpus đang phục vụ. Đây là báo cáo audit, không phải báo cáo sửa lỗi.

Branch `main`, HEAD `9730e282bf0e16f6fea3db2fee301173017820a8`; baseline `5c8124c` tồn tại. Các commit `627be4e`, `4e64f97`, `9730e28` lần lượt chứa Đợt 1–3; Đợt 4 và gỡ Zep nằm trong working tree. [Status lúc bắt đầu](post-fix-review-2026-11-18-evidence/initial-status.txt). **Working tree thay đổi đồng thời trong khi audit:** sau các probe xuất hiện chỉnh sửa `backend/src/health/tools.py`, OCR config/Compose/client/tests, `frontend/package.json`, xóa các fixture eval và thêm test. Không có snapshot bất biến; kết quả dưới đây gắn với thời điểm chạy, không khẳng định mọi kết quả đại diện tree cuối. Không tự hoàn nguyên các thay đổi đó.

## Phạm vi và độ sâu

| Phân hệ / luồng | Độ sâu thực tế |
|---|---|
| Auth → chat → safety → graph → retrieval → composer → citation | Đọc producer–consumer chọn lọc, regression backend, HTTP loopback; provider/search giả; chưa duyệt toàn bộ từng dòng |
| Profile/consent → measurement/progress; check-in | Đọc API/schema/UI; HTTP thật với SQLite cô lập, user tổng hợp; không PostgreSQL |
| Local memory | Đọc API/store/chat/retention; unit SQLite và TestClient; không Celery/PostgreSQL thật |
| Corpus → chunk → staging → Qdrant/BM25 → eval | Đọc các entrypoint, lifecycle, search, provenance; unit và Qdrant local in-memory; probe trộn release giả; không ghi corpus thật |
| OCR upload → extraction → xác nhận → lưu | Đọc gateway/service/UI, unit và probe Paddle/LLM giả; HTTP gateway với upstream giả; chưa browser upload/readback |
| Frontend | Adapter và các component chính, 14 test Node + SSR, lint/typecheck/build; browser chỉ mở trang, không hoàn thành tương tác do backend cô lập không kết nối từ tab |
| Infra, scripts, dependency, docs | Kiểm kê và đọc cấu hình liên quan; Compose config, npm audit, Python grammar; không review mọi file/migration |

## R01–R13 và Zep

Tầng test được nêu là kết quả mới trong lượt; tất cả runtime đều không đại diện deployment thật.

| ID | Nguyên nhân cũ → source/thay đổi hiện tại | Regression/kết quả mới | Kết luận/giới hạn |
|---|---|---|---|
| R01 | Overlap bỏ phủ định → `harness/guards.py`, composer thêm kiểm câu, số, polarity, citation và cache version | Suite phase02 đạt trong 326 test; probe 14 câu: chặn hai chiều phủ định và số/đơn vị mẫu, nhưng 3 câu sai được nhận và 1 diễn đạt đúng bị từ chối | **Sửa chưa đủ**, xem F1; không chứng minh entailment |
| R02 | Timeout provider không theo budget → `harness/budget.py`, `llm/client.py` chia sẻ monotonic deadline, SDK retry=0 | Unit mock; HTTP chậm summarize 504 ~0,5s, retry hai call trong ~1s | Chưa xác minh mọi provider/DB thật; `memory/chat.py` gọi DB trước khi kiểm budget, timeout DB cố định |
| R03 | Blocking I/O gây nghẽn → `core/execution.py`, API dùng lane giới hạn | HTTP search/summarize bão hòa: urgent P95 8,163ms và BMI 65,339ms, N=30 mỗi loại; timeout và admission phục hồi; OCR làm urgent 1.505ms | **Còn lỗi F4**; một mẫu OCR không là P95; disconnect worker vẫn hoàn tất |
| R04 | null thành 0, bỏ partial, PBF mặc định nam → `frontend/src/lib/api.ts`, dashboard/classifiers | 14 regression frontend gồm SSR và mapper đạt; source clear header khi list rỗng | Còn F6 chuỗi trắng; chưa browser xóa/readback |
| R05 | Adapter làm rơi safety, form sai nghĩa → `ProfileAndGoals.tsx`, adapter/SafetyBanner | HTTP SQLite check-in urgent 201, đọc lại urgent; SSR banner test đạt | Chưa kiểm chứng thao tác browser đầy đủ |
| R06 | CLI ghi alias phục vụ → `corpus_lifecycle.py`, importer/pipeline/task | Suite staging và Qdrant local-memory đạt; kiểm alias và physical trong fixture | Lock chỉ đảm bảo khi dùng cùng thư mục; còn khe TOCTOU nếu không chung mount; chưa kiểm mọi writer đồng thời trên Qdrant server |
| R07 | Seed tự gán approved/guideline → `rag/provenance.py`, registry và pipeline | Regression cũ đạt nhưng forged stamp qua registry rỗng | **Còn lỗi F2**; chưa có review y khoa thực |
| R08 | Backend Compose trỏ `ocr-api`, OCR service `ocr-paddle-api` | Source Compose backend vẫn cố định `http://ocr-api:18100`; OCR Compose đổi trong lúc audit nên phải xác minh alias/network trên snapshot cuối | Chưa chứng minh DNS thực; env_file bị `environment` ghi đè |
| R09 | Validator so value với raw_text do LLM tự sinh → OCR extractor | Bốn probe giả: bịa cả value/raw, nhầm metric, sai đơn vị, span không tồn tại đều được chấp nhận là draft | **Còn lỗi F5**, xác nhận người dùng vẫn bắt buộc |
| R10 | Đọc sai `{items}`, nuốt 401/403 → frontend adapter/profile | Regression mapper, auth event và component đạt | Chưa browser với auth/consent thật |
| R11 | UI đọc content/score khác excerpt/retrieval_score → adapter/CitationsView | SSR regression excerpt, ID, URL scheme đạt; không trình bày score là xác suất | Chưa browser với evidence provider thật |
| R12 | API/task đếm batch lỗi thành thành công → `jobs/tasks.py`, Qdrant client, API receipt | Unit failure và Qdrant local-memory đạt | Chưa fault injection qua Qdrant server/API thật, mọi writer chưa được chứng minh |
| R13 | Fixture/snapshot lệch, BM25 không gắn release → manifest/fingerprint/search/eval | Eval preflight exit 2 mismatch; probe trộn old/new cho `hybrid` | **Còn lỗi F3**; không có metric mới; fixture bị thay đổi đồng thời sau khi chạy |
| Zep | SDK/recall/sync/job ngoài → đã gỡ các module/dependency/route | 326 backend test gồm subprocess block SDK và local facts lifecycle; source còn `zep_memory` là denylist và legacy JSON compatibility | SQLite/mock không chứng minh PostgreSQL/Celery thực. Không suy ra dữ liệu từng gửi sang Zep đã xóa |

## Findings có reproduction

**F1 — P0: claim sai vẫn được gắn supported.** `backend/src/harness/guards.py:570` kiểm tập số và entity rồi lexical overlap; không gắn từng số với đối tượng hoặc quan hệ chủ–vị. Chạy [source_probes.py](post-fix-review-2026-11-18-evidence/source_probes.py): nguồn “SMM 30 kg và BFM 20 kg”, câu đảo thành “SMM 20 kg và BFM 30 kg [1]” được supported; tương tự đảo nam/nữ, đảo chủ–vị. Expected từ chối. Có một paraphrase đúng bị inconclusive; không phải validator luôn từ chối. Tác động: câu y khoa sai có citation có thể tới composer. Sửa nhỏ: fail closed khi không xác định được liên kết metric–value/chủ thể–quan hệ, thêm test cặp đảo và paraphrase đúng; không gọi đây là giải quyết entailment tổng quát.

**F2 — P0: self-declared review vượt registry.** `backend/src/rag/provenance.py:489` tin stamp `verified` nếu các trường tự nhất quán, không tra registry; `citation_checker.py` dùng kết quả đó cho gate medical caution. Probe với registry hoàn toàn rỗng, document/reviewer/review ID tự dựng và hai hash giống nhau được admit `verified`. Expected từ chối hoặc xác minh record/hashes bằng registry tin cậy. Không chứng minh dữ liệu thật đã bị giả. Sửa: resolve stamp về registry và ràng buộc document/version/hash, thêm test payload giả, hash stale, registry rỗng.

**F3 — P0: release chưa xác minh vẫn được trộn.** `backend/src/rag/search.py:538` trả `synced=true` khi không có lý do mismatch, kể cả `status=unverified` và BM25 không có physical binding; `hybrid_search` chỉ chặn khi `synced=false`. Probe tạo BM25 old, alias physical-new và dense giả new: hai version cùng trả `retrieval_mode=hybrid`. Snapshot local tại lúc probe 4.405 chunks, version `2026.1`, không có physical binding trong metadata. Expected refuse hoặc dense-only/BM25-only có nhãn khi không chứng minh đồng release. Test legacy snapshot, alias swap, hash/ID khác nhau nhưng count bằng nhau. Đây là fixture, không có Qdrant write thật.

**F4 — P0: OCR chiếm AnyIO pool khiến urgent chờ.** `backend/src/api/inbody_ocr.py:42` là route sync chờ OCR tối đa 100s trong default pool; `auth/context.py` auth dependency cũng dùng pool đó. HTTP loopback thực, SQLite và OCR upstream giả: 40 OCR đang chờ, urgent trả 200 sau 1.505ms (lần trước 1.279ms); expected bypass tải nặng. N=1 mỗi lần, không phải P95. Giới hạn OCR riêng hoặc async transport, bảo đảm auth urgent còn capacity; test tải đồng thời và timeout/cleanup.

**F5 — P0: OCR không grounding.** `ocr-paddle-services/src/inbody_ocr/inbody/extractor.py:78` chỉ so số trong `raw_text` do LLM trả, không kiểm OCR lines/label/unit; bốn probe synthetic đều nhận giá trị sai, status vẫn `needs_confirmation`. Không chứng minh đã tự lưu sai. Cần đối chiếu evidence line/page/label/unit, xử lý mâu thuẫn và giữ raw gốc sau sửa; test cả nhầm cột/range và browser confirm/readback.

**F6 — P1: chuỗi chỉ khoảng trắng thành 0.** `frontend/src/lib/api.ts:42` kiểm `val === ''` trước `trim`, sau đó `Number('')` ra 0. JSON `"   "` ở metric có thể hiển thị 0 thay missing; số 0 thật phải vẫn hợp lệ. Kiểm chuỗi sau trim trước Number; test mapper và KPI consumer. Đây là boundary input lỗi, không nói backend hiện phát chuỗi này.

**F7 — P1: client disconnect không hủy server work.** Trong HTTP probe, client timeout 80ms khi summarize đang chạy; lane vẫn active=1, abandoned=0, `completed_total` tăng sau upstream kết thúc. Capacity không bị trả sớm và phục hồi, nhưng server không nhận biết disconnect, công việc vẫn chạy; với chat có thể tiếp tục side effect tùy thời điểm. Expected đánh dấu hủy/không chạy stage hoặc ghi sau ngắt khi có thể. Thêm test HTTP disconnect và kiểm tra side effects. Không khẳng định mọi disconnect dẫn tới ghi dữ liệu.

**F8 — P2: dependency và tài liệu lệch.** `npm audit` mới báo 14 high, cùng chuỗi dev tooling dẫn tới `picomatch` GHSA-fc5q-39xc-vjpf, không suy ra 14 lỗ hổng độc lập hoặc runtime exploit. `README.md:205` vẫn ghi metric nghiệm thu cũ không có cấu hình/release tương ứng; roadmap dòng 75–76 còn mô tả cũ. `pip check` host có xung đột gói toàn cục, không quy cho backend image. Rà soát lockfile/advisory và cập nhật số đo có provenance; không tự nâng package trong audit.

## Kiểm thử mới

- Backend: `python -m pytest backend/tests/unit backend/tests/integration -q -p no:cacheprovider --basetemp .audit-post-fix-tmp/backend-rerun`: **326 passed, 3 warnings**, Python host 3.13.2; SQLite/mocks + Qdrant local in-memory. Lần đầu 315 passed/11 errors do thư mục basetemp cha chưa có; sau tạo thư mục chạy lại đạt. Tree thay đổi sau đó.
- Pipeline: **13 passed** sau chạy lại; lần đầu 10 passed/3 errors cùng lỗi basetemp. OCR: **16 passed**, Paddle/LLM giả. Frontend lint, `tsc --noEmit --incremental false`, build exit 0; `tsx --test` **14 passed**, mock fetch + SSR. `npm audit` exit 1, 14 high như F8; phụ thuộc trạng thái trước thay đổi package đồng thời.
- Grammar Python 3.10 + compile trên host: **139 file, 0 lỗi**, không thực thi trong Python image. `pip_audit` chưa cài; `pip check` là môi trường host dùng chung.
- HTTP loopback: Uvicorn thật, SQLite tổng hợp, upstream Ollama/search/OCR giả. Đo N=30 mỗi loại urgent/BMI dưới tải search/summarize: P50/P95/max lần cuối **6,657/8,163/9,026 ms**, **51,352/65,339/74,138 ms**. Không quy thành gate deployment. Search/summarize timeout 504, hàng đợi đầy 503, worker thu hồi slot. Retry lỗi giả 2 call, degraded. Measurement 201/readback 200, owner khác 404; check-in 201/readback urgent. OCR gateway giả không tự thêm measurement; tổng số trong fixture có thể đã có từ lần chạy trước.
- Eval mặc định exit 2: fixture version không khớp snapshot tại thời điểm chạy; không có Recall@5, top-1, safety hit hay citation precision mới. Sau đó fixture bị xóa đồng thời, cần khôi phục/quyết định bởi chủ sở hữu trước eval lại.
- Docker Engine ban đầu lỗi, sau đó đã truy cập được 24.0.7; Compose `config --quiet` infra/backend/embedding/OCR exit 0, frontend exit 1 do thiếu `frontend/.env`. Chỉ validate cấu hình, không khởi động container hoặc xem dữ liệu/volume. Browser mở trang dev nhưng hiện mất kết nối backend; không có browser E2E.
- `git diff --check` báo `README.md:255` blank EOF có sẵn. [Log và JSON](post-fix-review-2026-11-18-evidence/) chứa fixture tổng hợp; không có secret.

## NOT_RUN và nghiệm thu

Không chạy PostgreSQL, Valkey, Celery/Beat, Qdrant HTTP, embedding BGE-M3, Paddle inference, LLM thật, browser xác thực/consent/OCR, migration/volume, multi-host, soak, backup/restore, accessibility hoặc eval có nhãn được review. Không gọi provider trả phí. Chưa có kết luận cross-user leak toàn hệ thống; một ca owner khác 404 trên SQLite không thay thế kiểm tra production.

| Gate | Kết luận |
|---|---|
| Source và regression | Nhiều ca đạt, nhưng F1–F7 còn; tree thay đổi đồng thời cần chốt snapshot và chạy lại |
| Runtime tích hợp | Chưa nghiệm thu; HTTP mới là loopback với SQLite/upstream giả |
| Agent P0 | Chưa nghiệm thu; test tải giới hạn đạt một số chỉ số nhưng OCR starvation tái hiện; chưa chứng minh deadline mọi đường và zero-call dưới mọi tải |
| RAG beta | Chưa nghiệm thu; không có metric hợp lệ cùng release và human review; F1–F3 |
| OCR E2E | Chưa nghiệm thu; F5, chưa Paddle/LLM/DB/browser thật |
| Production candidate | Chưa nghiệm thu; còn P0/P1 và thiếu auth/privacy/load/restore/browser gates |

Thứ tự: (1) cố định revision/working tree và giữ fixture/nhãn provenance; (2) sửa F1–F5, đặc biệt không cho claim/review/corpus giả được xem là verified và bảo vệ urgent khỏi OCR; (3) sửa F6–F8, kiểm memory/consent và cancellation; (4) chạy lại regression trên snapshot cố định, sau đó dựng stack cô lập và kiểm browser, PostgreSQL, Qdrant, model; (5) phát hành corpus có review và đánh giá holdout cùng release trước khi xét gate.

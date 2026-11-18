# Lộ trình triển khai Health/InBody Agent RAG

Tiến độ 2026-11-19: [Retrieval/resume đợt 3](../reports/upgrade-2026/retrieval-resume-phase3.md) **source-ready, chưa deploy**; raw-first, error/API, dedup/parent, pin xuyên query và resume có regression cô lập, toàn suite 478/478 đạt. Runtime thật và gate chất lượng corpus chưa chạy.

Tiến độ 2026-11-19: [Độ tin cậy evidence và claim](../reports/upgrade-2026/reliability-phase2.md) — sửa trust boundary review và các ca hoán đổi giá trị ở source, có regression composer/cache và urgent trong process; registry thật rỗng, binding chunk và đánh giá độc lập còn thiếu. Chưa deploy.

Tiến độ 2026-11-19: [Ổn định test đợt 1](../reports/upgrade-2026/test-stabilization-phase1.md) — người dùng xác nhận ngừng observability, import-missing, vector-reuse và evaluator cũ; các khẳng định lịch sử bên dưới về chúng không còn mô tả source hiện tại. Collection host, 351 unit và 1 integration Qdrant local đạt; Python 3.10/image và các khoảng trống privacy/eval còn mở. Chưa deploy.

Tiến độ 2026-11-18: [Embedding E5 small](../reports/upgrade-2026/embedding-e5-small-2026-11-18.md) đã có Qdrant staging và BM25 đồng bộ, sửa kiểm tra release ở source; **chưa activate alias hoặc deploy ứng dụng**.

**Trạng thái:** kế hoạch triển khai; chưa phải xác nhận tính năng đã hoàn tất.  
**Cập nhật:** 2026-07-30  
**Phạm vi:** đưa MVP Health/InBody RAG từ demo kỹ thuật thành sản phẩm có bằng chứng, an toàn, đo lường được và có giá trị theo dõi tiến bộ.

## Mục tiêu sản phẩm

Tiến độ mới 2026-09-29: [Bộ nhớ Day17 bốn lớp](09-day17-memory-completion-2026-09-29.md)
đã nối source/test (lịch sử; phần Zep đã bị gỡ ngày 2026-11-18, giữ lại hoàn toàn PostgreSQL local memory).

Tiến độ mới 2026-11-18: [Gỡ bỏ tích hợp Zep Cloud](../reports/upgrade-2026/remove-zep-2026-11-18.md)
đã gỡ hoàn toàn adapter (`zep_memory.py`, `sync.py`), dependency `zep-cloud`, biến `ZEP_*`, các route external memory (`/me/memory-consent`, `/me/memory/sync`, `DELETE /me/memory`), `use_zep_memory`/`memory_context`, và job `maintain_external_memory`; giữ nguyên toàn bộ bộ nhớ hội thoại, facts, consent và retention local trên PostgreSQL cùng tương thích đọc các khóa JSON legacy (không suy diễn dữ liệu phía Zep đã xóa). Kiểm chứng đạt **326 backend tests** (gồm subprocess chặn `zep_cloud` và chặn outbound network) + **13 pipeline tests**, 16/16 file đạt Python 3.10. **Đã gỡ tích hợp Zep ở source và kiểm thử liên quan; memory local PostgreSQL được giữ lại; chưa deploy hệ thống hiện hữu.**

Tiến độ mới 2026-10-01: [Cache câu trả lời RAG an toàn](11-safe-llm-response-cache.md)
đã nối vào Composer và có regression tests; **source-ready, chưa deploy**, chưa đo hit rate/latency
trên Redis và API runtime.

Tiến độ mới 2026-11-18: [Đợt 2 — Kiểm chứng câu trả lời & Provenance (R01, R07)](../reports/upgrade-2026/phase02-evidence-provenance-2026-11-18.md)
đã triển khai kiểm chứng claim/citation câu-với-câu (phủ định hai chiều, số/khoảng/đơn vị, đối tượng, điều kiện, modality, parent expansion, nâng version cache key `v2`) và registry review y khoa (`backend/data/medical_review_registry.json`, bỏ tự gán `guideline`/`approved`/ngày review mặc định, hạ nhãn legacy chưa xác minh và chặn vượt gate ở nhánh `medical_caution`); **Đợt 2 source-ready, chưa deploy; chưa review lại hoặc phát hành corpus.**

Tiến độ mới 2026-11-18: [Đợt 3 — Kiểm soát Thời gian Xử lý & Tải (R02, R03)](../reports/upgrade-2026/phase03-deadline-load-2026-11-18.md)
đã thống nhất deadline monotonic end-to-end (`backend/src/harness/budget.py`, truyền xuống Ollama/OpenAI/custom/normalize/router/rewrite/embedding/Qdrant/rerank/Tavily/Zep/DB/Celery, tắt SDK auto-retry chồng lớp và loại bỏ network probe ngoài budget khi lazy init), tách làn thực thi có giới hạn concurrency/queue (`backend/src/core/execution.py`) khỏi AnyIO threadpool, bổ sung rate limiter tách biệt (`backend/src/core/rate_limit.py`, Valkey Lua atomic + fail-closed production) và giữ bất biến `urgent` fast-path; đã vượt qua 308 backend unit/fast-path tests và 6/6 ca kiểm chứng **HTTP backend thật, upstream giả để fault injection** (urgent N=25 dưới tải chậm đạt P95 = 2,01 ms, 0 upstream call). **Đợt 3 source-ready; HTTP fault-injection cô lập đã kiểm tra; chưa deploy hệ thống hiện hữu.**

Tiến độ mới 2026-11-18: [Đợt 4 — Khép kín Vòng đời Corpus (R06, R12, R13)](../reports/upgrade-2026/phase04-corpus-lifecycle-2026-11-18.md)
đã áp dụng chính sách staging admission fail-closed + khóa ghi/activation dùng chung (`backend/src/rag/corpus_lifecycle.py`, `lifecycle_bridge.py`) trên mọi writer (API, Celery tasks, CLI `import_data`/`import_missing_vectors`/`reuse_qdrant_vectors`, `collection_admin`, `data_pipeline`), chuẩn hóa `WriteReceipt` trung thực theo `UpdateStatus` Qdrant và pre-upsert vector validation (chặn thiếu embedding/sai dim/`NaN`/`Inf`, API trả HTTP `502` thay vì `200 status=true`), nâng cấp resume kiểm `content_hash`/`corpus_version`/`embedding_fingerprint` + checkpoint nguyên tử, gắn kết corpus release manifest schema v2 với `chunk_set_fingerprint` đồng bộ Qdrant/BM25/request-pinning/response-cache/chặn `API_WORKERS > 1`, nâng cấp eval preflight (`evaluate_phase1.py`) và runbook blue/green (`docs/QDRANT_BLUE_GREEN_IMPORT.md`). Kiểm chứng đạt **330 backend tests** (gồm integration trên `QdrantClient(":memory:")` cô lập) + **13 pipeline tests**, 24/24 file hợp lệ Python 3.10. **Đợt 4 source-ready; chưa import/phát hành corpus thật; alias phục vụ chưa thay đổi.**

Kế hoạch thiết kế dữ liệu: [Database và data schema tổng thể](10-database-schema-master-plan.md)
— **đề xuất chờ duyệt**, gồm hiện trạng, mô hình đích, privacy lifecycle, migration/rollback,
kiểm thử và các hướng mở rộng tương lai; chưa thực hiện thay đổi database.

Đối chiếu source ngày 2026-10-11, rà soát lại ngày 2026-10-16: [Kiểm kê hệ thống trước khi thiết kế lại CSDL](12-database-current-state-audit-2026-10-11.md)
ghi luồng dữ liệu, 12 bảng nghiệp vụ, các bất biến cần bảo vệ và phần phải kiểm tra trên PostgreSQL live.
Lần rà soát 2026-10-16 xác nhận source-level auth/OCR/retention/corpus flow; Docker Engine/API/DB runtime
không truy cập được trong sandbox, nên schema live, ledger, counts, backup/restore và worker status vẫn **CHƯA BIẾT**.
Thiết kế ở [master plan](10-database-schema-master-plan.md) vẫn là **đề xuất chờ duyệt**; chưa đổi schema hay dữ liệu.

Sản phẩm không nên được định nghĩa là “một chatbot có nhiều agent”. Giá trị chính cần là:

1. Giúp người dùng hiểu dữ liệu InBody đã nhập/xác nhận.
2. Cho thấy xu hướng giữa các lần đo và dữ liệu nào làm cơ sở cho nhận định.
3. Đề xuất ăn uống/tập luyện tham khảo, có giới hạn an toàn.
4. Trả lời câu hỏi dựa trên nguồn truy xuất được, hoặc nói rõ khi thiếu bằng chứng.

## Thứ tự thực hiện bắt buộc

| Pha | Tài liệu | Mức cấp thiết | Lý do |
|---|---|---:|---|
| P0 | [00-p0-trust-rag-safety.md](00-p0-trust-rag-safety.md) | Khẩn cấp | Nếu nguồn, retrieval và safety chưa đáng tin, mở rộng chức năng sẽ làm tăng rủi ro. |
| P0 | [03-evaluation-and-acceptance.md](03-evaluation-and-acceptance.md) | Khẩn cấp | Không có benchmark thì không thể chứng minh các sửa đổi thực sự tốt hơn. |
| P1 | [01-p1-progress-and-personalization.md](01-p1-progress-and-personalization.md) | Cao | Đây là phần tạo giá trị khác biệt trực tiếp từ dữ liệu InBody. |
| P2 | [02-p2-ocr-privacy-and-live-web.md](02-p2-ocr-privacy-and-live-web.md) | Trung bình | OCR, dữ liệu nhạy cảm và web sống chỉ nên mở sau khi P0/P1 ổn định. |

## Quy tắc ra quyết định

- Không thêm agent mới nếu chưa có tác vụ, input, output và metric riêng của agent đó.
- Không gọi một kết quả là “đáng tin” chỉ vì vector similarity cao. Similarity chỉ là tín hiệu liên quan tài liệu, không phải xác suất đúng y khoa.
- Không chẩn đoán, kê đơn, đưa liều thuốc, hoặc thay thế bác sĩ.
- Câu có dấu hiệu cấp cứu phải đi bằng fast-path quyết định, không phụ thuộc LLM, RAG hay web search.
- Chỉ đưa một phase sang triển khai khi tiêu chí nghiệm thu của phase trước đã đạt.

## Tài liệu tham khảo đã khảo sát

- [InBody App](https://inbodyusa.com/inbody-app/): lịch sử đo, insight và theo dõi tiến độ.
- [Body Journey](https://bodyjourney.app/): progress tracking, kế hoạch tập/dinh dưỡng và hướng privacy-first.
- [Gymia](https://gymia.fit/): goal onboarding, workout/nutrition check-in và AI coach.
- [MedIntel RAG Chatbot](https://github.com/Gaggs-daggs/medintel-rag-chatbot): citation, uncertainty, RAGAS và cấu trúc RAG y tế.
- [WikiChat](https://github.com/stanford-oval/WikiChat): multilingual retrieval, BGE-M3, Qdrant, rerank, citation.
- [OpenAI Knowledge Retrieval](https://github.com/openai/openai-knowledge-retrieval): cấu hình retrieval, ingestion, chunking và evaluation.

## Hiện trạng cần lưu ý

- Ngày 2026-11-18 đã tạo staging Qdrant E5 384 chiều gồm 3.846 point; đã kiểm fingerprint và tìm kiếm trực tiếp. Chưa activate alias, chưa đồng bộ BM25 hoặc nghiệm thu ứng dụng; xem `docs/reports/upgrade-2026/embedding-e5-small-2026-11-18.md`.

Repo đã có FastAPI, LangGraph, Qdrant, BM25, safety tool, agent trace, `InBodyMeasurement` và test fast-path. Đây là nền tảng tốt. Tuy vậy trước khi mở rộng cần xác thực lại runtime sau các thay đổi hiện có:

- `POST /agent/answer` chưa trả `retrieved_docs` cho UI, dù state nội bộ có dữ liệu này.
- Composer nhận tài liệu RAG nhưng chưa có hợp đồng buộc citation theo từng nhận định.
- `initialize_from_vector_store(limit=1000)` cần được thay bằng scroll phân trang đủ corpus trước khi tuyên bố hybrid retrieval hoạt động đầy đủ.
- Báo cáo kiểm thử 2026-07-30 phản ánh một giai đoạn corpus đang ingest và latency cao; phải chạy lại benchmark sau khi chốt fast-path/index.

Các nhận định trên là các hạng mục kiểm tra/triển khai, không được đưa vào tài liệu marketing như thể đã hoàn thành.

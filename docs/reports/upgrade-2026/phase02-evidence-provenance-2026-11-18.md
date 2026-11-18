# Báo cáo Triển khai Đợt 2: Kiểm chứng Câu trả lời & Provenance (R01, R07)

- **Ngày thực hiện:** 2026-11-18
- **Tham chiếu đánh giá:** `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md` và `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`
- **Branch / HEAD baseline:** `main` @ `627be4e88afe9295a2425edac85244e5fc39acc7` (đã gồm Đợt 1 frontend contracts R04, R05, R10, R11)
- **Thay đổi có sẵn được giữ nguyên:** `README.md` (chỉnh sửa chưa commit của người dùng), `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md`, `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`
- **Trạng thái bàn giao:** **Đợt 2 source-ready, chưa deploy; chưa review lại hoặc phát hành corpus.**

---

## 1. Lỗi tái hiện trước sửa (In-Process Synthetic Probes)

### R01 — Guard và Composer chấp nhận claim đảo nghĩa nguồn dưới nhãn `supported`
- **Nguồn tổng hợp:** `"BMI không đủ để chẩn đoán sức khỏe."`
- **Câu trả lời cố ý sai:** `"BMI đủ để chẩn đoán sức khỏe [1]."`
- **Kết quả trước sửa:**
  - `verify_answer_claims`: `accepted = True`, `links = [{"claim_id": 1, "evidence_id": 1, "document_id": "doc-bmi", "chunk_id": "chunk-bmi-1"}]`.
  - `response_composer_agent`: giữ nguyên câu sai trong `final_answer`, trả `evidence_status = "supported"`, `links = 1`.
- **Nguyên nhân gốc:** Guard cũ (`backend/src/harness/guards.py`) dựa vào token overlap 65% trên toàn chunk và kiểm phủ định một chiều (chỉ bắt trường hợp claim thêm `"không"` khi nguồn không có, không bắt việc bỏ `"không"` khỏi nguồn, không tách câu/mệnh đề, không kiểm đơn vị đi kèm số, đối tượng, điều kiện áp dụng hay phạm vi parent expansion).

### R07 — Pipeline tự gán `source_tier=guideline`, `medical_review_status=approved` và ngày review mặc định
- **Probe trước sửa (`seed_document(SEED_DOCUMENTS[6])` với `source_url="internal_curated"`):**
  - Tự sinh `source_tier = "guideline"`, `medical_review_status = "approved"`, `review_status = "approved"`, `published_at = "2024-01-01T00:00:00Z"`, `reviewed_at = "2026-01-15T00:00:00Z"`, `publisher = "Sports nutrition principles"`.
- **Phát hiện bổ sung trong luồng raw ingestion:** `data_pipeline/src/ingestion/raw_loader.py` (`merge_inbody_medical_knowledge`) có fallback `or "approved"` cho `medical_review_status` khi trường nguồn thiếu.
- **Đứt gãy bảo toàn provenance:** `bm25_indexer.py` chỉ giữ provenance trong nested `metadata`; `search.initialize_from_vector_store()` chỉ lấy 6 trường cơ bản từ Qdrant payload và làm rơi toàn bộ metadata nguồn/review; `import_data.build_chunk_payloads()` làm rơi metadata nguồn khỏi `search_document`; `expand_parent_documents()` thay `content` bằng `parent_content` nhưng giữ nguyên `chunk_id` của child chunk.

---

## 2. Thiết kế triển khai & Giới hạn thực tế

### 2.1 R01 — Kiểm chứng Claim câu-với-câu, Liên kết Citation & Cache Policy

- **Kiến trúc kiểm chứng (`backend/src/harness/guards.py`, `backend/src/harness/layers/critic.py`):**
  - Tách câu bảo vệ số thập phân (`_split_sentences`), loại bỏ breadcrumb đầu chunk (`[Guide > Section]`) nhưng giữ nguyên citation `[n]`.
  - Phân loại câu rõ ràng theo 4 loại:
    1. `rag_claim` (mọi câu có `[n]` hoặc nêu khẳng định thực tế không thuộc 3 nhóm dưới): bắt buộc có `[n]` hợp lệ trỏ tới `evidence` đã admit.
    2. `safety_notice`: câu chứa `safety_result.disclaimer` / `recommended_action` hoặc khuyến cáo an toàn chuẩn (không chứa lời khuyên thay đổi thuốc/tập luyện nguy hiểm và không tự bịa số liệu lâm sàng) được giữ nguyên mà không bắt gắn citation RAG.
    3. `deterministic_tool`: câu báo kết quả phép tính phải khớp giá trị trong `tool_results` (sai số làm tròn `<= 0.05`); lệch số bị từ chối với `tool_value_mismatch`.
    4. `clarification_or_refusal`: câu hỏi bổ sung dữ liệu / lời từ chối phù hợp không bị ép dựng citation giả; Composer giữ lại câu hỏi/từ chối an toàn nhưng đặt `evidence = []`, `claim_evidence_links = []`, `evidence_status = "insufficient"` và không ghi cache.
  - **7 cổng kiểm tra trên cặp `(claim_sentence, matched_evidence_sentence)`** (so trên câu liên quan nhất trong chính `excerpt` đã truncate của evidence `[n]`, giúp phủ định ở câu khác trong cùng chunk không gây nhiễu):
    1. **Phủ định hai chiều & phạm vi mệnh đề:** chặn cả bỏ phủ định (`negation_dropped`), thêm phủ định (`negation_added`), đảo phạm vi phủ định giữa các mệnh đề trong câu ghép (`negation_scope_dropped` / `negation_scope_added`), và cặp từ trái nghĩa định hướng (`tăng/giảm`, `cao/thấp`, `đủ/thiếu`, `nên/tránh/cấm`, `an toàn/nguy hiểm`).
    2. **Số, khoảng giá trị & toán tử so sánh:** kiểm chính xác khoảng (`300-500 kcal`, `18.5-24.9`) và toán tử (`<`, `<=`, `>`, `>=`, `dưới`, `trên`).
    3. **Đơn vị đi kèm số:** gắn chuẩn đơn vị kế cận (`%`, `kg`, `g`, `g/kg`, `kcal`, `mmHg`, `mg/dL`, `mmol/L`, `cm`, `phút`, `buổi/tuần`, `level`, ...); `25 kg` không khớp `25%`.
    4. **Đối tượng / chủ thể:** kiểm nhóm dân số (`nam`/`nữ`, `trẻ em`/`người lớn`/`người cao tuổi`/`mang thai`/`châu Á`/bệnh lý) và thực thể chỉ số (`BMI`/`PBF`/`SMM`/`BFM`/`mỡ nội tạng`/`BIA`/`DXA`); chặn cả đổi đối tượng lẫn xóa giới hạn đối tượng.
    5. **Điều kiện áp dụng:** chặn bỏ mệnh đề điều kiện (`nếu`, `khi`, `trừ khi`, `chỉ khi`, `đối với`, `ở người`) và chặn khái quát hóa vô điều kiện (`mọi người`, `tất cả`, `luôn luôn`).
    6. **Mức độ khẳng định (Modality):** chặn nâng thông tin tham khảo/sàng lọc thành chẩn đoán/cam kết/kê đơn (`chắc chắn`, `khẳng định`, `chẩn đoán`, `chữa khỏi`, `cam kết`, `kê đơn`, `thay thế bác sĩ`).
    7. **Grounded lexical support có kiểm soát:** chỉ dùng overlap làm bước neo sau khi đã qua 6 cổng trên, kết hợp bảng tương đương từ vựng hẹp, tường minh (`biểu thị`/`phản ánh`/`cho biết` -> `là`, `tỉ lệ` -> `tỷ lệ`, tên đầy đủ chỉ số InBody). Khi không xác định được hỗ trợ đủ chặt, trả nội bộ `inconclusive` và fail-closed về `supported = False`.
- **Liên kết citation & Parent Expansion (`citation_checker.py`, `search.py`, `composer.py`):**
  - Citation `[1..k]` chỉ được cấp sau khi lọc injection, invalid, truncation (`max_chars`) và `max_docs`; context bị loại không bao giờ còn citation.
  - Khi mở rộng parent (`expand_parent_documents`), `chunk_id` của evidence là `parent_id` với `evidence_scope = "parent_section"` và `matched_child_chunk_id` lưu vết child gốc. Nếu claim chỉ có ở phần khác của parent (ngoài `child_excerpt`), `claim_evidence_links` gắn `chunk_id = parent_id`, `evidence_scope = "parent_section"`, `matched_child_chunk_id = None` — không gắn nhầm vào child chunk. Nếu `is_expanded_parent=True` nhưng thiếu `parent_id`, hệ thống hạ về `child_content` thay vì phát tán nội dung mở rộng không có provenance.
- **Response Cache Policy (`core/response_cache.py`, `agents/composer.py`):**
  - Nâng `RESPONSE_CACHE_SCHEMA_VERSION` từ `health-inbody-rag-response-v1` lên `health-inbody-rag-response-v2` và đưa `CLAIM_VALIDATION_POLICY_VERSION` + `PROVENANCE_POLICY_VERSION` vào key hash để vô hiệu hóa các cache entry cũ mà không xóa cache production.
  - Câu trả lời bị từ chối hoặc không có `claim_evidence_links` đã verify không được ghi cache; cache hit không vượt qua `check_claims_detailed` bị từ chối và evict ngay.
- **Giới hạn rõ ràng của thiết kế R01:**
  - Bộ kiểm chứng hiện tại là deterministic rule-based ở mức câu/mệnh đề, **không phải** mô hình suy diễn ngữ nghĩa (NLI/entailment) tiếng Việt hoàn chỉnh.
  - Nó có thể từ chối thận trọng (false negative -> `inconclusive` -> fallback an toàn) đối với các diễn giải phức tạp, tái cấu trúc câu sâu hoặc tổng hợp nhiều câu ngoài bảng tương đương hẹp.
  - Ngược lại, các biến thể ngôn ngữ tinh vi nằm ngoài tập từ điển/quy tắc (như ẩn dụ, phủ định ngầm hiếm gặp hoặc thực thể bệnh lý mới chưa nằm trong danh mục) vẫn cần đánh giá định kỳ bởi con người trên bộ eval thực tế.

### 2.2 R07 — Provenance, Registry Review & Xử lý Metadata Legacy

- **Nguồn chân lý quản lý bởi dự án:**
  - Tạo `backend/data/medical_review_registry.json` (`schema_version = 1`, `registry_version = "2026-11-18"`, `is_synthetic_fixture = false`, `reviewers = {}`, `reviews = []` — **trống trung thực**, không dựng hồ sơ giả cho 56 record hay 24 seed).
  - Tạo module dùng chung `backend/src/rag/provenance.py` (kèm bridge `data_pipeline/src/processors/provenance_bridge.py` để `data_pipeline` và `backend` dùng chung một nguồn logic duy nhất).
- **Tách biệt 4 khái niệm:**
  1. **Schema validation:** kiểm tra cấu trúc bản ghi, độ dài, `content_type`.
  2. **Privacy review (`privacy_review_status`, `data_scope`):** kiểm tra PII/phạm vi công khai trong `corpus_policy.py` — tuyệt đối không nâng `medical_review_status`.
  3. **Source tier (`source_tier`, `source_tier_verified`):** không tự gán `"guideline"` cho seed hay tài liệu chỉ có URL uy tín; chỉ gán `source_tier` khi được xác minh trong hồ sơ review (`verified_source_tier`).
  4. **Medical/content review (`medical_review_status`, `review_verification_status`):** chỉ đạt `approved` + `verified` khi có hồ sơ hợp lệ trong registry với đầy đủ `review_id`, `reviewer_id` (đang active trong `reviewers`), `review_role`, `review_scope`, `reviewed_at` (ISO), `document_id`, `content_hash` (SHA-256 64-hex khớp nội dung hiện tại), `decision = "approved"`, và `notes`/`rationale`.
- **Phát hiện review đã cũ & chặn fixture giả:**
  - Khi nội dung thay đổi làm `document_content_hash != reviewed_content_hash`, trạng thái chuyển sang `medical_review_status = "stale_review"`, `review_verification_status = "stale_content_mismatch"`, `reviewed_at = None`, `source_tier = None` — không kế thừa `approved` bản cũ.
  - Registry hoặc bản ghi có `is_synthetic_fixture = true` bị `load_review_registry(..., allow_synthetic=False)` từ chối để ngăn fixture test bị đóng gói thành hồ sơ thật.
- **Xử lý metadata legacy:**
  - Các tài liệu/payload cũ tự khai `medical_review_status = "approved"` hoặc `"reviewed"` nhưng không có hồ sơ tương ứng trong registry được hạ idempotent thành `medical_review_status = "unverified_legacy"`, `review_verification_status = "unverified_legacy"`, `reviewed_at = None`, `source_tier = None`, `source_tier_verified = False` (giữ `legacy_claimed_review_status` để audit).
  - Các seed chưa review có `medical_review_status = "provisional"`, `review_verification_status = "unreviewed"`, `source_url = None` (nếu là `"internal_curated"`), `publisher = None`, `published_at = None`, `reviewed_at = None`.
  - **Cổng nhạy cảm (`medical_caution`):** trong `composer._set_evidence_state`, khi `safety_result.risk_level == "medical_caution"`, bật `require_verified_medical_review = True`. Tài liệu legacy `approved` chưa xác minh bị loại khỏi context; hệ thống không gọi LLM để tổng hợp khuyến nghị mà trả lời giới hạn thiếu dữ liệu kèm giữ nguyên `recommended_action` an toàn.
- **Bảo toàn provenance xuyên suốt:**
  - Đồng bộ truyền đủ `PROVENANCE_METADATA_FIELDS` qua `raw_loader.py` -> `corpus_processor.py` -> `markdown_chunker.py` -> `bm25_indexer.py` / `qdrant_indexer.py` / `import_data.py` -> `vector_metadata.py` -> `search.py` (`_normalize_document`, `initialize_from_vector_store`, `expand_parent_documents`) -> `citation_checker.build_evidence()`.

---

## 3. Danh sách File Thay đổi

### File mới
1. `backend/data/medical_review_registry.json` — Registry hồ sơ duyệt y khoa có version (hiện trống `reviews: []`).
2. `backend/src/rag/provenance.py` — Logic chuẩn hóa, băm nội dung, xác minh review registry, phát hiện stale hash và hạ legacy.
3. `data_pipeline/src/processors/provenance_bridge.py` — Bridge import dùng chung `backend/src/rag/provenance.py` cho `data_pipeline`.
4. `backend/tests/unit/test_phase02_claim_and_provenance.py` — 20 regression tests chuyên sâu cho R01 & R07 (guard, composer, cache, parent expansion, provenance, legacy, sensitive branch).
5. `docs/reports/upgrade-2026/phase02-evidence-provenance-2026-11-18.md` — Báo cáo bàn giao Đợt 2.

### File đã sửa
6. `backend/src/harness/guards.py`
7. `backend/src/harness/layers/critic.py`
8. `backend/src/harness/layers/citation_checker.py`
9. `backend/src/core/response_cache.py`
10. `backend/src/agents/composer.py`
11. `backend/src/rag/search.py`
12. `backend/src/rag/vector_metadata.py`
13. `backend/src/rag/corpus_policy.py`
14. `backend/src/pipelines/import_data.py`
15. `data_pipeline/src/processors/corpus_processor.py`
16. `data_pipeline/src/ingestion/raw_loader.py`
17. `data_pipeline/src/chunkers/markdown_chunker.py`
18. `data_pipeline/src/indexers/bm25_indexer.py`
19. `data_pipeline/src/indexers/qdrant_indexer.py`
20. `backend/tests/unit/test_import_data.py` (cập nhật test strict validation phân biệt self-claimed vs registry-verified)
21. `backend/tests/unit/test_greeting_safety_regression.py` (gắn synthetic verified review metadata cho fixture `synthetic-safety` để giữ đúng mục đích test provider/unsafe_output trên nhánh `medical_caution`)
22. `data_pipeline/tests/test_data_pipeline.py` (cập nhật assertion seed cũ đang khóa lỗi R07 + thêm 3 test provenance end-to-end)
23. `docs/implementation-roadmap/README.md` (cập nhật tiến độ thực tế Đợt 2)

*(Không sửa dữ liệu raw/generated trong `data_pipeline/dataset/` hoặc `backend/data/generated/`; không sửa frontend vì API contract `citations`/`evidence` giữ nguyên tương thích và chỉ bổ sung trường additive.)*

---

## 4. Kết quả Kiểm thử Trước / Sau

| Hạng mục kiểm chứng | Lệnh chạy | Kết quả trước sửa | Kết quả sau sửa |
|---|---|---|---|
| Probe tái hiện R01 (guard + composer đảo nghĩa) | Python in-process probe | Guard `accepted=True`; Composer giữ câu sai, `evidence_status="supported"`, `links=1` | Guard `status="unsupported"`, `reasons=['epistemic_escalation', 'negation_dropped']`; Composer thay bằng limitation, `evidence_status="insufficient"`, `links=[]` |
| Probe tái hiện R07 (`seed_document` với `internal_curated`) | Python in-process probe | `source_tier="guideline"`, `medical_review_status="approved"`, ngày publish/review giả | `medical_review_status="provisional"`, `review_verification_status="unreviewed"`, `source_tier=None`, `source_url=None`, `publisher=None`, `published_at=None`, `reviewed_at=None` |
| Backend unit + fast-path integration | `$env:PYTHONPATH=(Resolve-Path 'backend/src').Path; $env:DATABASE_URL='sqlite://'; python -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider` | 264 unit passed (baseline trước thêm test Đợt 2) | **291 passed**, 0 failed (2 warnings `on_event`) |
| Data pipeline tests | `python -m pytest data_pipeline/tests -q -p no:cacheprovider` | 10 passed (bao gồm assertion cũ khóa R07) | **13 passed**, 0 failed |
| Syntax & Python 3.10 grammar (`backend` image target) | `py_compile` + `ast.parse(..., feature_version=(3, 10))` trên 24 file | — | **PASS (24/24 files)** |
| Whitespace / diff hygiene | `git diff --check -- backend/ data_pipeline/` | — | **PASS (0 issues)** |

---

## 5. Minh bạch về Mock, Môi trường & Phần Chưa Chạy

- **Sử dụng mock / không gọi mạng / không gọi model thật:** Toàn bộ 304 test chạy in-process bằng fixture tổng hợp và mock cho LLM (`openai_chat_complete`), Qdrant client, embedder và response cache; dùng SQLite in-memory cho kiểm thử API/session. **Không** gọi provider LLM trả phí, **không** gửi request mạng, **không** ghi Qdrant/PostgreSQL/Redis thật.
- **Đã xác minh:**
  - Source code, Python 3.10 grammar/syntax, unit tests, fast-path integration tests, pipeline unit tests, và luồng end-to-end trong process (`retrieved doc -> admission -> evidence -> claim validation -> composer -> cache` và `raw/seed -> normalize -> chunk -> BM25/Qdrant payload -> search -> evidence`).
- **Chưa chạy / ngoài phạm vi Đợt 2:**
  - Chưa build/restart Docker container và chưa chạy HTTP smoke test trên runtime thật.
  - Chưa chạy lại benchmark retrieval/citation trên tập eval có nhãn người review và chưa đối chiếu corpus version (thuộc đợt dữ liệu/eval R13).
  - Chưa re-embed, re-import hoặc thay đổi bất kỳ collection Qdrant hay file generated nào.
- **Tuyên bố giới hạn bắt buộc:** Kết quả 304 regression tests **không** chứng minh câu trả lời đúng y khoa ngoài thực tế, **không** chứng minh đã loại bỏ hoàn toàn hallucination, **không** chứng minh đạt citation precision ≥ 95%, và **không** đưa hệ thống lên trạng thái production-ready.

---

## 6. Việc Còn Cần Con Người Có Chuyên Môn Review

1. **24 tài liệu `SEED_DOCUMENTS`** trong `data_pipeline/src/processors/corpus_processor.py` hiện ở trạng thái `provisional` / `unreviewed` (đặc biệt các tài liệu `medical_safety` như red flags tập luyện, bệnh nền, chống ăn kiêng cực đoan).
2. **56 bản ghi legacy có nhãn `approved`/`guideline` cũ** trong `data_pipeline/dataset/raw/inbody_medical_knowledge/` (hiện sẽ bị hạ xuống `unverified_legacy` và bị chặn ở nhánh `medical_caution` cho đến khi có hồ sơ review thật).
3. **Các tài liệu còn lại trong 1.009 tài liệu corpus** (đặc biệt phân bố mất cân đối: chỉ 11 tài liệu `medical_safety`, 35 `inbody_metric`, 558 `nutrition`, 404 `exercise`, 1 `general_health`).
4. **Quy trình ký duyệt thực tế:** Chỉ người có chuyên môn phù hợp (bác sĩ/chuyên gia dinh dưỡng/y học thể thao được dự án ghi danh vào `reviewers` trong `backend/data/medical_review_registry.json`) mới được cấp entry `reviews[]` gắn đúng `document_id`, `content_hash`, `review_scope`, `reviewed_at`, `decision` và `notes`.

---

## 7. Đề xuất Riêng cho Đợt Cập nhật Corpus về Sau (Chưa Thực hiện Import)

1. Khép kín staging guard và write receipts trước khi import (R06, R12, R13).
2. Thực hiện review chuyên môn theo mức ưu tiên: (a) nhóm `medical_safety` và chống chỉ định InBody/tập luyện trước để mở khóa nhánh `medical_caution` một cách có bằng chứng, (b) nhóm `inbody_metric`, (c) nhóm `nutrition`/`exercise`.
3. Cập nhật `backend/data/medical_review_registry.json` với hồ sơ review thật đã ký, chạy `data_pipeline` ra artifact mới với `corpus_version` mới (không ghi đè bản đang phục vụ).
4. Import vào **physical staging collection mới**, chạy `audit_qdrant_metadata.py` và đối chiếu đồng bộ BM25 snapshot + Qdrant point count/hash trước khi chuyển alias blue/green và cập nhật eval fixture cùng phiên bản.

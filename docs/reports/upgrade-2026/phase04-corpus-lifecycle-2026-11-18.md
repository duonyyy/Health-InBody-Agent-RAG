# Báo cáo Triển khai Đợt 4: Khép kín Vòng đời Corpus (R06, R12, R13)

- **Ngày thực hiện:** 2026-11-18
- **Tham chiếu đánh giá:** `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md`, `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`, `docs/QDRANT_BLUE_GREEN_IMPORT.md`, `docs/reports/upgrade-2026/phase02-evidence-provenance-2026-11-18.md`, `docs/reports/upgrade-2026/phase03-deadline-load-2026-11-18.md`
- **Branch / HEAD baseline:** `main` @ `9730e282bf0e16f6fea3db2fee301173017820a8` (đã gồm Đợt 1–3)
- **Thay đổi có sẵn được giữ nguyên:** `README.md` (chỉnh sửa chưa commit của người dùng), `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md`, `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`
- **Trạng thái bàn giao:** **Đợt 4 source-ready; chưa import/phát hành corpus thật; alias phục vụ chưa thay đổi.**

---

## 1. Kiểm kê Entrypoint Đọc/Ghi và Lỗi Tồn tại trên Baseline

Trước khi sửa, rà soát toàn bộ caller trong `backend/` và `data_pipeline/` xác nhận cả 3 nhóm vấn đề vẫn tồn tại trên revision `9730e28`:

| Nhóm | Entrypoint / Vị trí | Hành vi cũ | Đã bảo vệ trong Đợt 4 |
|---|---|---|---|
| **API ghi corpus** | `POST /collection/create`, `/document/create`, `/documents/index`, `/data/import` (`backend/src/api/app.py`) | Pydantic mặc định `collection_name=nmk_chatbot_active`; chỉ kiểm allowlist tĩnh (không kiểm actual alias target của Qdrant); trả HTTP `200 {"status": true}` dù writer báo lỗi batch | Bắt buộc chọn tường minh `collection_name`; kiểm allowlist + live Qdrant alias topology (offload lên `probe` lane, fail-closed `503`); trả HTTP `502` với receipt thất bại/partial, `409` khi lock conflict |
| **Celery / Task indexing** | `index_document_v2`, `index_health_documents` (`backend/src/jobs/tasks.py`) | Mặc định ghi `DEFAULT_COLLECTION_NAME`; không kiểm staging admission; `index_health_documents` đếm `len(statuses)` là `indexed` bất kể lỗi và gọi `initialize_search_index` vào RAM; phụ thuộc trực tiếp `langchain.text_splitter` | Bắt buộc staging admission + write lease; dùng `split_document_safe`; trả `WriteReceipt` trung thực (`indexed == committed_documents`, không mutate BM25 serving RAM); `raise_on_error=True` ném `QdrantWriteError` để Celery không báo `SUCCESS` |
| **CLI backend import** | `import_data.py`, `import_missing_vectors.py`, `reuse_qdrant_vectors.py` (`backend/src/pipelines/`) | `import_data` & `import_missing_vectors` mặc định `nmk_chatbot_active` và thiếu `import sys`; resume chỉ kiểm point ID không kiểm `content_hash`/version; `reuse_qdrant_vectors` chỉ kiểm `vector_size` không kiểm `embedding_fingerprint` | Cùng cổng `verify_staging_write_target` (fail-closed), write lease theo batch, resume đối chiếu `content_hash` + `corpus_version` + `embedding_fingerprint`, checkpoint nguyên tử chỉ tiến sau commit; `reuse_qdrant_vectors` kiểm bắt buộc `embedding_fingerprint`; CLI exit khác `0` khi lỗi |
| **Qdrant low-level & Admin CLI** | `create_collection`, `add_vector`, `delete_vectors`, `activate_collection_alias` (`backend/src/rag/qdrant/client.py`, `collection_admin.py`) | `create_collection`/`add_vector`/`delete_vectors` không chặn serving alias hoặc physical target; `add_vector` trả list raw gom lỗi; `activate_collection_alias` chỉ kiểm `points_count`, không khóa ghi đồng thời | Mọi hàm ghi qua `verify_staging_write_target`; `add_vector` kiểm alignment/dim/finite trước upsert và diễn giải đúng `UpdateStatus`; `activate_collection_alias` giữ `activation.lock` (chặn khi có `write.lock`), kiểm release manifest + `chunk_set_fingerprint` + vector config + giữ nguyên collection cũ để rollback |
| **Pipeline offline** | `data_pipeline/run_pipeline.py`, `qdrant_indexer.py`, `bm25_indexer.py`, `pipeline_config.py`, `corpus_processor.py` | Mặc định `nmk_chatbot_active`; hard-code `corpus_version="2026.1"`; tự fallback sang dry-run khi Qdrant/embedder offline; `QdrantIndexer` dùng `zip` có thể bỏ rơi chunk khi thiếu embedding | Dùng chung policy qua `lifecycle_bridge.py`; bỏ mặc định serving alias và bỏ hard-code `2026.1`; từ chối ghi thật nếu dịch vụ offline khi không truyền `--dry-run`; dry-run không ghi vector giả (`indexed_points=0`, `topology_verified=false`); xuất BM25 gắn `chunk_set_fingerprint` và release manifest |
| **Runtime retrieval & Cache** | `backend/src/rag/search.py`, `agents/nodes/rag.py`, `agents/composer.py`, `core/response_cache.py`, `scripts/build_bm25_snapshot.py` | Chỉ kiểm tên alias `collection_name` và `document_count` khi load BM25; không pin physical collection đầu request; không chặn multi-worker BM25; cache key chưa gắn `release_id`/`physical_collection`/`chunk_set_fingerprint` | Pin physical collection đầu request; đối chiếu live alias target & manifest; mặc định `RETRIEVAL_MISMATCH_POLICY=refuse` (503 ở `/search` và `/health/ready`); gắn đúng `retrieval_mode` (`hybrid`/`dense_only`/`bm25_only`); chặn `API_WORKERS > 1` khi bật BM25; gắn đủ release fingerprint vào response cache key |
| **Eval harness** | `backend/scripts/evaluate_phase1.py` | Chưa kiểm release manifest/fingerprint; không tách đơn vị nhãn `document` vs `chunk`; fixture v1 trộn tên capability nội bộ vào `selected_agents` | Preflight kiểm manifest + version + `chunk_set_fingerprint` + snapshot/suite SHA-256 + `label_granularity` (`document`/`chunk`) + phân biệt `public_specialists` vs `capabilities`; lỗi preflight exit code `2`; tách bạch `offline_bm25` (`bm25_only`) với các nhánh `NOT_RUN` (`dense_real`, `hybrid_real`, `citation_claim_quality`) |

---

## 2. R06 — Chính sách Admission Dùng chung & Khóa Ghi/Activation

Module trung tâm mới: **`backend/src/rag/corpus_lifecycle.py`** (bridge sang `data_pipeline` qua **`data_pipeline/src/processors/lifecycle_bridge.py`**; tái xuất ở **`backend/src/rag/corpus_policy.py`**).

### 2.1 Admission Fail-Closed (`verify_staging_write_target`)
- Mọi đích ghi phải chỉ định **physical staging collection** tường minh và hợp lệ theo regex naming. Không mặc định ghi vào serving alias (`nmk_chatbot_active`).
- Mọi tên thuộc tập serving alias bảo vệ (`QDRANT_COLLECTION_ALIAS`, `QDRANT_COLLECTION_NAME`, `CORPUS_PROTECTED_ALIASES`, mặc định gồm `nmk_chatbot_active`) đều bị chặn **ngay cả khi xuất hiện trong `CORPUS_STAGING_COLLECTIONS`**.
- Với mọi thao tác ghi thật (`dry_run=False`), hệ thống **bắt buộc** gọi `qdrant_client.get_aliases()`:
  - Nếu không gọi được Qdrant hoặc lỗi mạng -> ném `CorpusTopologyUnavailableError` (**fail-closed**, không chạy create/embed/upsert).
  - Nếu đích ghi là tên một alias đang tồn tại trong Qdrant HOẶC là **physical collection mà bất kỳ alias nào đang trỏ tới** -> ném `CorpusAdmissionError` (allowlist không thể vượt qua bảo vệ actual alias target).
- Chế độ `dry_run=True` xác thực tên/schema offline và ghi tường minh `topology_verified=false`, `warning="Offline dry-run: chưa xác minh Qdrant alias topology thật."`.

### 2.2 Khóa Ghi vs Activation (`CorpusLeaseManager`) và Phạm vi Bảo đảm
- **Cơ chế:** Khóa nguyên tử bằng file lock (`os.open(..., O_CREAT | O_EXCL)` + `fsync`) trong thư mục dùng chung `CORPUS_LOCK_DIR` (mặc định `backend/artifacts/corpus_locks`, được mount chung vào cả `chatbot-api` và `chatbot-worker` qua `.:/usr/src/app/`), kèm TTL và heartbeat gia hạn theo batch.
- **Bất biến được thực thi:**
  1. Writer giữ `collection.<name>.write.lock` trước khi tạo/embed/upsert -> `activate_collection_alias` đọc thấy write lease còn hạn sẽ lập tức từ chối (`CorpusLockError`).
  2. Activation giữ `collection.<name>.activation.lock` -> mọi writer mới vào collection đó bị từ chối (`CorpusLockError`).
  3. Trước **mỗi batch upsert**, writer gọi `verify_and_renew_write_lease` để xác minh lease còn thuộc sở hữu của mình **và** kiểm tra lại `get_aliases()` trực tiếp trên Qdrant -> nếu collection vừa được activate bởi tiến trình ngoài, writer dừng ngay trước batch tiếp theo.
- **Giới hạn đã ghi nhận rõ:**
  - Bảo đảm loại trừ lẫn nhau tuyệt đối trong phạm vi mọi tiến trình/container cùng mount `CORPUS_LOCK_DIR`.
  - Nếu một tiến trình chạy trên host hoàn toàn độc lập không mount chung `CORPUS_LOCK_DIR`, cơ chế kiểm lại `get_aliases()` trước mỗi batch vẫn chặn các batch sau khi alias đã chuyển, nhưng vẫn còn cửa sổ TOCTOU hẹp giữa lúc kiểm `get_aliases()` và lúc RPC `upsert` tới Qdrant.

---

## 3. R12 — Hợp đồng Writer, Pre-Upsert Validation & Partial Semantics

- **Kiểm tra trước upsert (`validate_embeddings_alignment`, `validate_vectors_before_upsert`):**
  - Chặn lệch số lượng embedding so với chunk đầu vào (không dùng `zip` làm rơi âm thầm phần đuôi).
  - Chặn sai dimension (`vector_size`), giá trị không phải số thực (kể cả `bool`), `NaN`, `+Inf`, `-Inf`, point ID rỗng/không hợp lệ và payload lệch `corpus_version`/`embedding_fingerprint`.
- **Diễn giải đúng semantics `qdrant-client` (1.19.1) với `wait=True` (`interpret_qdrant_upsert_result`):**
  - `UpdateStatus.COMPLETED` -> `committed_points` (server xác nhận đã apply với `wait=True`; vẫn phân biệt với `verified_points` chỉ được xác nhận sau bước scroll/verify toàn bộ collection).
  - `UpdateStatus.ACKNOWLEDGED` -> `acknowledged_points` & `unconfirmed_points` (`ok=False`, `status="incomplete"`, **không** tính là committed).
  - `UpdateStatus.WAIT_TIMEOUT` hoặc exception -> `failed_points` (`ok=False`, `status="failed"` hoặc `"partial"` nếu các batch trước đã commit).
- **Chính sách partial write:**
  - Nếu batch 1 commit được $N_1$ điểm và batch 2 lỗi, receipt ghi trung thực `committed_points=N_1`, `failed_points=N_2`, `partial_write=True`, `rollback_performed=False`, `ok=False`, `status="partial"`. Không bao giờ tuyên bố đã rollback giả và không tự xóa collection phục vụ.
  - CLI trả exit code `1`; API `/document/create`, `/documents/index`, `/data/import` trả HTTP `502` với `status=false` (không bao giờ HTTP `200` `status=true`); Celery task với `raise_on_error=True` ném `QdrantWriteError`.

---

## 4. Checkpoint, Resume Đúng Nội dung & Vector Reuse

- **Định danh canonical:** Giữ tách biệt `document_id` (ID tài liệu gốc), `chunk_id` (ID chunk duy nhất), `qdrant_point_id` (`uuid5(NAMESPACE_URL, chunk_id)`), `content_hash` (SHA-256 chunk) và `document_content_hash` (SHA-256 tài liệu). Không thay `document_id` bằng `chunk_id`.
- **Content-verified resume (`get_collection_point_fingerprints`, `check_existing_point_conflict`):**
  - Chỉ bỏ qua (`skipped_reasons.already_present_matching_content`) khi điểm tồn tại có **cùng** `content_hash`, `corpus_version` và `embedding_fingerprint`.
  - Nếu cùng point ID nhưng khác `content_hash`, `corpus_version`, hoặc `embedding_fingerprint` (hoặc thiếu `content_hash`) -> báo **conflict** (`conflict_points > 0`, `status=False`), không bỏ qua như thành công.
- **Checkpoint nguyên tử (`atomic_write_json` — temp file + `fsync` + `os.replace`):**
  - Chỉ tiến `last_successful_upsert_line` sau khi batch nhận xác nhận commit.
  - Lưu `resume_signature` (`collection_name`, `corpus_version`, `data_file_sha256`, `chunk_size`, `chunk_overlap`, `vector_size`, `embedding_fingerprint`, `splitter_version`). Nếu bất kỳ tham số nào đổi, `verify_resume_compatibility` từ chối resume cũ và yêu cầu tạo staging release mới. Không lưu secret hay dữ liệu sức khỏe thô trong manifest/checkpoint.
- **Vector reuse (`reuse_qdrant_vectors.py`):** Bắt buộc khớp `embedding_fingerprint` (tính từ định danh model/revision/dimension/distance/normalize không nhạy cảm đọc từ env, không hard-code tên model trong `backend/src`) — từ chối reuse nếu chỉ trùng dimension hoặc thiếu fingerprint.

---

## 5. R13 — Release Manifest, Đồng bộ Qdrant/BM25/Runtime/Cache & Ownership

### 5.1 Release Manifest Schema (`schema_version = 2`)
Gắn kết tường minh chuỗi: `source_manifest` (path, SHA-256, counts) → `chunk_manifest` (`expected_count`, `unique_document_count`, `unique_chunk_count`, `chunk_set_fingerprint`) → `chunking_config` → `embedding_config` (`fingerprint`, `model_identifier`, `model_revision`, `vector_size`, `distance`, `normalize_embeddings`) → `physical_collection` & `serving_alias` → `bm25_artifact` (path, SHA-256, `schema_version`, `tokenizer_version`, `chunk_set_fingerprint`) → `provenance_summary` (giữ nguyên chuẩn Đợt 2, không tự dựng `approved`/`guideline`) → `eval_binding` → `write_receipt` → `build_status` / `publication_status` / `verification` / `previous_release`.

- **`chunk_set_fingerprint`:** SHA-256 trên tập đã sắp xếp các tuple `(qdrant_point_id, chunk_id, document_id, content_hash)` — phát hiện ngay trường hợp cùng số lượng điểm (`count`) nhưng sai bất kỳ ID hay nội dung nào.

### 5.2 Đồng bộ Runtime, Pinning, Cache và Sở hữu Lexical Index
- **Request pinning (`backend/src/rag/search.py`):** Đầu mỗi yêu cầu `hybrid_search`, hệ thống resolve actual alias target hiện tại và pin `pinned_collection` cho toàn bộ request. Nếu alias chuyển sang release mới giữa chừng, nhánh dense vẫn truy vấn đúng `pinned_collection` đã pin, không trộn 2 corpus trong cùng một kết quả.
- **Xử lý mismatch:**
  - Nếu BM25 snapshot (dù mang cùng tên alias `nmk_chatbot_active`) trỏ sai `physical_collection`, `release_id`, `corpus_version` hoặc `chunk_set_fingerprint` so với Qdrant/manifest:
    - `RETRIEVAL_MISMATCH_POLICY=refuse` (mặc định): ném `CorpusReleaseMismatchError` (`/search` trả `503`; `/health/ready` trả `503` với `dependencies.corpus_release_sync=false`; `rag_agent` ghi lỗi rõ ràng và hạ về thiếu bằng chứng thay vì trộn corpus).
    - `RETRIEVAL_MISMATCH_POLICY=dense_only` hoặc `bm25_only`: chỉ chạy nhánh được phép, gắn `retrieval_mode="dense_only"` / `"bm25_only"` và `release_mismatch_degraded=True`. Không bao giờ gán nhãn `"hybrid"` khi chỉ một nhánh tham gia.
  - Snapshot hỏng/ghi dở (gzip cắt cụt, JSON lỗi) khiến `load_search_snapshot` trả `False`, ghi `snapshot_error`, và `/health/ready` từ chối ready (`503`).
- **Response Cache (`core/response_cache.py`, `agents/composer.py`):**
  - Bổ sung `release_cache_policy` (`corpus-release-binding-v1`) cùng `release_id`, `physical_collection`, `chunk_set_fingerprint`, `snapshot_sha256` vào `corpus_fingerprint` của cache key (giữ tương thích `RESPONSE_CACHE_SCHEMA_VERSION=v2`, vô hiệu hóa không phá hủy các entry cũ mà không xóa cache production).
  - Không ghi/đọc cache khi `release_sync_status == "mismatch"`.
- **Sở hữu Lexical Index (`API_WORKERS`):**
  - Ghi rõ trong `get_search_stats()`: `lexical_index_owner="single_api_process_in_memory"`, `multi_worker_supported=False`.
  - `validate_lexical_worker_config()` chạy ngay lúc startup API: chặn `API_WORKERS > 1` khi `BM25_AUTOLOAD=true` (trừ khi cố ý bật cờ `ALLOW_UNSUPPORTED_MULTI_WORKER_BM25=true`). Giữ `API_WORKERS=1` trong `backend/docker-compose.yml` và `.env.example`.

---

## 6. Eval trên Đúng Release (`backend/scripts/evaluate_phase1.py`)

- Preflight kiểm bắt buộc: `corpus_version` khớp giữa fixture/snapshot/manifest, `chunk_set_fingerprint` khớp, `bm25_artifact.sha256` khớp, `eval_binding.suite_sha256` khớp (nếu đã pin), mọi ID đều tồn tại trong đúng không gian nhãn (`document_id` cho `label_granularity="document"`, `chunk_id` cho `label_granularity="chunk"`), cấm trộn 2 loại nhãn trong cùng ca.
- Routing phân biệt tường minh `expected.public_specialists` (`InBodyAgent`, `LifestyleAgent`, `KnowledgeAgent`) với `expected.capabilities` (`InBodyAgent`, `NutritionAgent`, `TrainingAgent`, `RAGAgent`, `WebSearchAgent`, `GeneralChatAgent`); chặn capability nội bộ nằm trong `public_specialists`.
- Báo cáo tách biệt rõ: `offline_bm25` (`retrieval_mode="bm25_only"`), `dense_real` (`NOT_RUN`), `hybrid_real` (`NOT_RUN`), `rerank_ab` (`NOT_RUN` trừ khi truyền `--include-offline-rerank-ab`), `citation_claim_quality` (`NOT_RUN`, không suy từ retrieval score hay tồn tại citation ID). Trạng thái mặc định: `publication_status="PROVISIONAL_OFFLINE_ONLY"`.
- Lỗi preflight in JSON lý do ra `stderr` và thoát mã `2`. Chạy thử trên snapshot local hiện tại (`2026.1`) với `cases_v1.jsonl` (`2026-07-30-v2`) dừng đúng như thiết kế với `exit=2` (`fixture corpus_version does not match snapshot`). Không sửa chuỗi version fixture để giả pass.

---

## 7. Kết quả Kiểm thử & Phân tách Môi trường Thật / Giả

| Hạng mục | Tầng môi trường | Lệnh chạy | Kết quả |
|---|---|---|---|
| Backend unit + fast-path integration + Phase 4 unit (17 test mới) | **Fake Qdrant / Mock fault injection** + SQLite in-memory + FastAPI TestClient | `$env:PYTHONPATH=(Resolve-Path 'backend/src').Path; $env:DATABASE_URL='sqlite://'; python -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider` | **329 passed**, 0 failed |
| Isolated Blue/Green Lifecycle Integration | **Qdrant local engine thật (`QdrantClient(':memory:')`, `qdrant-client 1.19.1`)** với synthetic JSONL + real BM25 gzip snapshot + atomic locks | `python -m pytest backend/tests/integration/test_phase04_qdrant_local_lifecycle.py -q -p no:cacheprovider` | **1 passed** (10 bước E2E: v1 activate → block alias & physical target → v2 import → idempotent resume → BM25 + manifest → integrity verify → alias switch giữ v1 → live hybrid search → rollback alias & mismatch refusal → verified fingerprint vector reuse) |
| Tổng tổ hợp pytest backend (330 tests) | Fake client + local in-memory Qdrant | Chạy chung trong 1 phiên | **330 passed**, 0 failed (3 warnings: 2 `on_event` cũ + 1 local-Qdrant payload index warning) |
| Data pipeline tests | Synthetic data + fake Qdrant client | `python -m pytest data_pipeline/tests -q -p no:cacheprovider` | **13 passed**, 0 failed |
| Syntax & Python 3.10 grammar check (`backend` image target) | Static AST (`feature_version=(3, 10)`) + `py_compile` | Kiểm tra 24 file source/test Đợt 4 | **PASS (24/24 files)** |
| Eval preflight trên snapshot local hiện có | Read-only trên `cases_v1.jsonl` + `bm25_snapshot.json.gz` | `python backend/scripts/evaluate_phase1.py` | **Exit code `2`** (`fixture corpus_version does not match snapshot`) — fail-closed đúng thiết kế |
| Diff whitespace hygiene | Git working tree | `git diff --check -- backend/ data_pipeline/ docs/` | **PASS (0 issues)** |
| Docker / Qdrant HTTP server thật / Alias runtime thật / HTTP smoke sau deploy | **NOT_RUN** | `docker info` trả lỗi không kết nối được Docker daemon (`//./pipe/docker_engine` không tồn tại) | **NOT_RUN** — không dùng fake-client hay in-memory Qdrant thay bằng chứng Qdrant HTTP/Docker thật |

*(Ghi chú: Không đo và không công bố các metric RAG beta mới — Recall@5, strict top-1, Safety Hit@5, dense/hybrid thật, rerank A/B thật, citation precision — vì chưa import/phát hành corpus mới có review chuyên môn và chưa chạy trên runtime thật.)*

---

## 8. Danh sách File Thay đổi & Rollback

### File mới
1. `backend/src/rag/corpus_lifecycle.py` — Lõi dùng chung: admission fail-closed, `CorpusLeaseManager`, validation vector, `WriteReceipt`, `chunk_set_fingerprint`, embedding fingerprint, checkpoint/resume, release manifest schema v2.
2. `data_pipeline/src/processors/lifecycle_bridge.py` — Bridge chia sẻ `corpus_lifecycle.py` cho `data_pipeline/`.
3. `backend/tests/unit/test_phase04_corpus_lifecycle.py` — 17 regression tests chuyên sâu cho R06, R12, R13 và Eval.
4. `backend/tests/integration/test_phase04_qdrant_local_lifecycle.py` — Integration test 10 bước trên `QdrantClient(":memory:")` cô lập.
5. `docs/reports/upgrade-2026/phase04-corpus-lifecycle-2026-11-18.md` — Báo cáo bàn giao Đợt 4.

### File đã sửa
6. `backend/src/rag/corpus_policy.py`
7. `backend/src/rag/vector_metadata.py`
8. `backend/src/rag/qdrant/client.py`
9. `backend/src/rag/qdrant/collection_admin.py`
10. `backend/src/rag/search.py`
11. `backend/src/core/response_cache.py`
12. `backend/src/agents/composer.py`
13. `backend/src/agents/nodes/rag.py`
14. `backend/src/jobs/tasks.py`
15. `backend/src/api/app.py`
16. `backend/src/pipelines/import_data.py`
17. `backend/src/pipelines/import_missing_vectors.py`
18. `backend/src/pipelines/reuse_qdrant_vectors.py`
19. `backend/scripts/build_bm25_snapshot.py`
20. `backend/scripts/evaluate_phase1.py`
21. `data_pipeline/configs/pipeline_config.py`
22. `data_pipeline/src/processors/corpus_processor.py`
23. `data_pipeline/src/indexers/bm25_indexer.py`
24. `data_pipeline/src/indexers/qdrant_indexer.py`
25. `data_pipeline/run_pipeline.py`
26. `backend/tests/unit/test_import_data.py` (cập nhật mock topology/fingerprints cho 2 test cũ để phù hợp fail-closed R06)
27. `backend/tests/unit/test_corpus_privacy.py` (cập nhật mock live alias topology cho test HTTP cũ)
28. `data_pipeline/tests/test_data_pipeline.py` (cập nhật 2 test cũ cho dry-run trung thực và staging admission)
29. `docs/QDRANT_BLUE_GREEN_IMPORT.md` (cập nhật runbook 8 bước có preflight, release manifest, BM25 verify, eval, activation và rollback)
30. `docs/implementation-roadmap/README.md` (cập nhật tiến độ Đợt 4)

*(Không sửa dữ liệu trong `backend/data/`, `data_pipeline/dataset/`, `backend/evals/phase1/cases_v1.jsonl`, cấu hình env riêng, Docker Compose, hay database schema.)*

### Rollback trong phạm vi source/artifact
- Toàn bộ thay đổi chỉ nằm ở mã nguồn, test và tài liệu; không tạo/sửa collection Qdrant thật, không chuyển alias, không sửa snapshot BM25 local.
- Có thể rollback nguyên vẹn bằng cách revert diff Đợt 4 về revision `9730e282bf0e16f6fea3db2fee301173017820a8` (giữ nguyên `README.md` và báo cáo reassessment) mà không ảnh hưởng Đợt 1–3 hoặc dữ liệu runtime.
- Với vận hành khi phát hành thật sau này, xem bước 7 của `docs/QDRANT_BLUE_GREEN_IMPORT.md` (`collection_admin.py rollback-alias --previous-collection ...`).

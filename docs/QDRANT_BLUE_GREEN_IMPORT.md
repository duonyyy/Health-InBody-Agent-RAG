# Quy trình Phát hành Corpus Blue/Green (Qdrant + BM25 + Release Manifest)

> **Cập nhật 19/11/2026:** Runbook này chưa thể thực thi đầy đủ: evaluator Phase 1,
> import-missing và vector-reuse đã được quyết định ngừng hỗ trợ; các script audit và
> build snapshot được nhắc bên dưới cũng đang thiếu. Không chạy các lệnh tham chiếu
> script thiếu và không activate dựa trên runbook này; cần cập nhật và kiểm chứng gate
> đánh giá mới trước khi phát hành. Xem báo cáo ổn định test Phase 1.

Tài liệu này là **runbook chuẩn có preflight** để xây dựng, kiểm chứng và phát hành một
corpus release mới mà **không bao giờ ghi đè collection đang phục vụ** và **không để
Qdrant lệch phiên bản với BM25 snapshot**.

> [!IMPORTANT]
> - Không chạy lệnh import vào serving alias (`nmk_chatbot_active`) hoặc physical collection
>   mà alias đang trỏ tới. Mọi writer (API, Celery task, CLI backend, `data_pipeline`) đều
>   bắt buộc kiểm tra staging admission và fail-closed khi không xác minh được topology Qdrant.
> - Không tự động chuyển alias sau upsert, và không activate chỉ vì Qdrant báo `green` hoặc
>   khớp `points_count`.
> - Không xóa collection phiên bản trước trong quy trình này để giữ khả năng rollback có kiểm soát.
> - **Ghi chú Đợt 4 (2026-11-18):** Các lệnh dưới đây là quy trình chuẩn bị sẵn; **chưa thực thi
>   import/phát hành corpus thật và chưa thay đổi alias phục vụ**.

---

## Quy ước đặt tên cho một release mới

Thay `<VERSION>` và `<STAGING_COLLECTION>` bằng phiên bản bất biến cụ thể của đợt phát hành
(ví dụ `2026-11-18-v1` và `nmk_chatbot_collection_v20261118_bge_m3_1024`):

```powershell
$CORPUS_VERSION     = "2026-11-18-v1"
$STAGING_COLLECTION = "nmk_chatbot_collection_v20261118_bge_m3_1024"
$SERVING_ALIAS      = "nmk_chatbot_active"
$RELEASE_MANIFEST   = "/usr/src/app/artifacts/releases/${CORPUS_VERSION}.release.json"
$IMPORT_MANIFEST    = "/usr/src/app/artifacts/imports/${CORPUS_VERSION}.import.json"
$BM25_SNAPSHOT      = "/usr/src/app/data/generated/bm25_snapshot_${CORPUS_VERSION}.json.gz"
```

---

## Bước 1 — Preflight: Kiểm tra import jobs, collection, alias, status, count và manifest hiện hữu

Chụp nguyên trạng hệ thống đang phục vụ trước mọi thao tác và lưu lại bằng chứng:

```powershell
# 1.1 Kiểm tra alias hiện tại và physical collection đang phục vụ
Invoke-RestMethod http://127.0.0.1:6333/aliases | ConvertTo-Json -Depth 10
Invoke-RestMethod http://127.0.0.1:6333/collections | ConvertTo-Json -Depth 10

# Ghi lại tên physical collection hiện hữu ($PREVIOUS_COLLECTION) và thống kê chi tiết
Invoke-RestMethod "http://127.0.0.1:6333/collections/${PREVIOUS_COLLECTION}" | ConvertTo-Json -Depth 10

# 1.2 Kiểm tra không có job import hoặc write/activation lock đang chạy
docker top chatbot-api
docker top health-embedding-api
docker exec chatbot-api ls -la /usr/src/app/artifacts/corpus_locks 2>$null

# 1.3 Kiểm tra trạng thái BM25/readiness hiện hành
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Depth 6
Invoke-RestMethod http://127.0.0.1:8000/health/ready | ConvertTo-Json -Depth 6
```

**Điều kiện đi tiếp:**
- Không có tiến trình `import_data.py`, `import_missing_vectors.py`, `reuse_qdrant_vectors.py`, hoặc `run_pipeline.py` đang chạy.
- Không có lock file đang hoạt động trên collection đích.
- `update_queue.length == 0` trên Qdrant.
- Đã ghi lại `$PREVIOUS_COLLECTION`, `points_count`, `status`, và manifest/log cuối.

---

## Bước 2 — Chuẩn bị physical staging collection mới

Tạo physical staging collection tách biệt hoàn toàn với `$SERVING_ALIAS` và `$PREVIOUS_COLLECTION`:

```powershell
docker exec chatbot-api python src/rag/qdrant/collection_admin.py create `
  --collection $STAGING_COLLECTION `
  --vector-size 1024
```

Lệnh sẽ tự kiểm tra admission (`verify_staging_write_target`), tạo collection Cosine 1024 chiều và tạo đầy đủ payload indexes (`content_type`, `document_id`, `chunk_id`, `corpus_version`, `release_id`, `embedding_fingerprint`, `content_hash`, metadata review).

Nếu client timeout sau khi collection đã được tạo phía server, chạy lại idempotent:

```powershell
docker exec chatbot-api python src/rag/qdrant/collection_admin.py ensure-indexes `
  --collection $STAGING_COLLECTION
```

---

## Bước 3 — Validate nguồn, chunks, provenance và dry-run offline

1. Đảm bảo `backend/data/medical_review_registry.json` chứa hồ sơ duyệt y khoa thật (được ký bởi chuyên gia có danh tính, khớp `document_id` và `content_hash` hiện hành; tuyệt đối không dùng synthetic fixture hay tự gán `approved`/`guideline`).
2. Chạy dry-run offline để kiểm schema, privacy/PII, provenance và đếm số chunk + `chunk_set_fingerprint` (lưu ý: dry-run báo `topology_verified=false` và **không** ghi vào Qdrant):

```powershell
docker cp `
  "data_pipeline/dataset/processed/embedding_documents.jsonl" `
  "chatbot-api:/tmp/embedding_documents_${CORPUS_VERSION}.jsonl"

docker exec chatbot-api python src/pipelines/import_data.py `
  --data-file "/tmp/embedding_documents_${CORPUS_VERSION}.jsonl" `
  --collection $STAGING_COLLECTION `
  --corpus-version $CORPUS_VERSION `
  --dry-run
```

*(Thêm `--require-trusted-source-metadata` khi bắt buộc mọi tài liệu đều đã có hồ sơ review y khoa xác minh trong registry.)*

---

## Bước 4 — Import vào staging và kiểm tra Write Receipt

Thực thi import vào `$STAGING_COLLECTION` với write lease, checkpoint nguyên tử và release manifest:

```powershell
docker exec chatbot-api python src/pipelines/import_data.py `
  --data-file "/tmp/embedding_documents_${CORPUS_VERSION}.jsonl" `
  --collection $STAGING_COLLECTION `
  --skip-collection-create `
  --corpus-version $CORPUS_VERSION `
  --embedding-batch-size 8 `
  --batch-size 50 `
  --manifest-file $IMPORT_MANIFEST `
  --release-manifest-file $RELEASE_MANIFEST
```

**Kiểm tra bắt buộc sau lệnh:**
- Exit code phải là `0`.
- Trong `$IMPORT_MANIFEST`: `status == true`, `ok == true`, `error_count == 0`, `conflict_count == 0`, `fatal_error == null`.
- Trong `write_receipt`: `ok == true`, `status == "committed"`, `failed_points == 0`, `unconfirmed_points == 0`, `partial_write == false`.
- Nếu gặp sự cố hạ tầng giữa chừng:
  - Không tự ý xóa collection phục vụ.
  - Chỉ resume bằng `--skip-existing-points --manifest-file $IMPORT_MANIFEST` khi nguồn, `chunk_size`, `chunk_overlap`, và `embedding_fingerprint` **không đổi** (nếu đổi, resume sẽ bị từ chối và phải tạo release/collection staging mới).
  - Nếu có `conflict_count > 0` (cùng point ID nhưng khác `content_hash` hoặc `corpus_version`), tuyệt đối không bỏ qua; phải xử lý gốc và build staging release mới.

---

## Bước 5 — Verify Qdrant collection + BM25 snapshot + Release Manifest

1. Tạo BM25 snapshot đồng bộ trực tiếp từ `$STAGING_COLLECTION` (hoặc từ cùng bộ chunk trong `data_pipeline` với `--corpus-version $CORPUS_VERSION --staging-collection $STAGING_COLLECTION`):

```powershell
docker exec chatbot-api python scripts/build_bm25_snapshot.py `
  --collection $STAGING_COLLECTION `
  --corpus-version $CORPUS_VERSION `
  --output $BM25_SNAPSHOT
```

2. Xác minh toàn vẹn Qdrant (vector size, point count, `chunk_set_fingerprint`, `corpus_version`, payload indexes) khớp với `$RELEASE_MANIFEST`:

```powershell
docker exec chatbot-api python src/rag/qdrant/collection_admin.py verify `
  --collection $STAGING_COLLECTION `
  --release-manifest $RELEASE_MANIFEST
```

3. Đối chiếu `chunk_set_fingerprint` và `document_count` giữa:
   - `chunk_manifest.chunk_set_fingerprint` trong `$RELEASE_MANIFEST`
   - `chunk_set_fingerprint` trả về từ `collection_admin.py verify`
   - `chunk_set_fingerprint` trong `$BM25_SNAPSHOT`

4. Kiểm tra metadata provenance (read-only):

```powershell
docker exec chatbot-api python scripts/audit_qdrant_metadata.py `
  --collection $STAGING_COLLECTION
```

---

## Bước 6 — Chạy Eval trên đúng Release

Chạy harness evaluation gắn chặt với `$BM25_SNAPSHOT` và `$RELEASE_MANIFEST` (preflight tự dừng với exit code `2` nếu lệch version, hash, fingerprint, đơn vị label document/chunk, hoặc ID không tồn tại):

```powershell
docker exec chatbot-api python scripts/evaluate_phase1.py `
  --cases evals/phase1/cases_v1.jsonl `
  --snapshot $BM25_SNAPSHOT `
  --release-manifest $RELEASE_MANIFEST `
  --split development `
  --output "/usr/src/app/artifacts/evals/${CORPUS_VERSION}_dev_eval.json"
```

**Quy tắc công bố benchmark:**
- Báo cáo offline BM25 luôn ghi rõ `retrieval_mode: "bm25_only"`, `dense_real: NOT_RUN`, `hybrid_real: NOT_RUN`, `citation_claim_quality: NOT_RUN` và `publication_status: "PROVISIONAL_OFFLINE_ONLY"` nếu chưa có đủ review chuyên môn hoặc đo retrieval/citation thật trên runtime.
- Không sửa riêng chuỗi `corpus_version` trong fixture để ép preflight xanh.
- Giữ split `holdout` độc lập; chỉ chạy `--split holdout` ở bước nghiệm thu cuối sau khi đóng băng heuristics/ranker.

---

## Bước 7 — Chuẩn bị Activation và Kế hoạch Rollback

Chỉ kích hoạt khi:
- Bước 1–6 đều đạt.
- Không còn write lease nào trên `$STAGING_COLLECTION`.
- `$PREVIOUS_COLLECTION` vẫn còn nguyên vẹn (tuyệt đối không xóa).

Lệnh chuyển alias nguyên tử (tự giữ `activation.lock`, kiểm manifest, count, vector config, `chunk_set_fingerprint` và payload indexes):

```powershell
docker exec chatbot-api python src/rag/qdrant/collection_admin.py activate-alias `
  --collection $STAGING_COLLECTION `
  --alias $SERVING_ALIAS `
  --release-manifest $RELEASE_MANIFEST
```

Đồng bộ cấu hình runtime trong `backend/.env` (trên môi trường triển khai thật, giữ `API_WORKERS=1` vì BM25 hiện sở hữu in-memory trong một process):

```dotenv
QDRANT_COLLECTION_NAME=nmk_chatbot_active
QDRANT_COLLECTION_ALIAS=nmk_chatbot_active
CORPUS_VERSION=2026-11-18-v1
BM25_SNAPSHOT_PATH=/usr/src/app/data/generated/bm25_snapshot_2026-11-18-v1.json.gz
CORPUS_RELEASE_MANIFEST_PATH=/usr/src/app/artifacts/releases/2026-11-18-v1.release.json
RETRIEVAL_MISMATCH_POLICY=refuse
API_WORKERS=1
```

### Lệnh Rollback có kiểm soát (nếu cần quay về release trước)

```powershell
docker exec chatbot-api python src/rag/qdrant/collection_admin.py rollback-alias `
  --previous-collection $PREVIOUS_COLLECTION `
  --alias $SERVING_ALIAS `
  --expected-points $PREVIOUS_EXPECTED_POINTS
```

Sau rollback alias, trỏ lại `CORPUS_VERSION`, `BM25_SNAPSHOT_PATH`, `CORPUS_RELEASE_MANIFEST_PATH` về bản của `$PREVIOUS_COLLECTION` và recreate `chatbot-api` + `chatbot-worker`. Collection mới không bị xóa tự động để phục vụ điều tra sau sự cố.

---

## Bước 8 — Kiểm tra HTTP/Runtime sau Activation thật

Chỉ sau khi recreate riêng `chatbot-api` và `chatbot-worker` (không cần restart Qdrant) và xác nhận HTTP thật mới cập nhật trạng thái phát hành thành `published`:

1. `GET /health` và `GET /health/ready` trả `200`, `dependencies.corpus_release_sync == true`, `corpus_release.physical_collection == $STAGING_COLLECTION`.
2. Smoke test tối thiểu theo `AGENTS.md`: lời chào, BMI `72 kg / 170 cm`, đau ngực + khó thở (`urgent`), InBody, nutrition, exercise, safety retrieval (0 recipe trong top 5), và input âm trả `422`.
3. Xác nhận response cache không trả câu trả lời cũ từ release trước (cache key v3 gắn `release_id`, `physical_collection`, `chunk_set_fingerprint`).

---

## Giới hạn sở hữu Lexical Index (BM25)

- Snapshot `.json.gz` được ghi nguyên tử để tăng tốc khởi động và khóa phiên bản, nhưng chỉ mục BM25 vẫn nằm **in-memory trong từng process API**.
- `API_WORKERS=1` là cấu hình duy nhất được hỗ trợ khi bật `BM25_AUTOLOAD=true`; hệ thống sẽ chủ động chặn khởi động (`validate_lexical_worker_config`) nếu cấu hình `API_WORKERS > 1` mà chưa tắt `BM25_AUTOLOAD`.
- Khi cần scale nhiều API worker nhất quán về sau, cần tách lexical search sang engine/dịch vụ dùng chung (ví dụ Qdrant sparse vectors hoặc OpenSearch/Meilisearch) ở đợt riêng.

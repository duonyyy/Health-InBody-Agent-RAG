# Quy trình import Qdrant blue/green

Tài liệu này dùng để nạp lại corpus mà không ghi đè collection đang phục vụ.
Collection cũ chỉ bị ngừng sử dụng sau khi collection mới đủ dữ liệu và được
kiểm tra. Không xóa collection cũ trong quy trình này.

## Tên dùng trong đợt hiện tại

```text
Collection cũ:       nmk_chatbot_collection
Collection mới:      nmk_chatbot_collection_v20260730_bge_m3_1024
Alias runtime mới:   nmk_chatbot_active
Corpus version:      2026-07-30-v2
Số point dự kiến:    23608
Vector size:         1024
```

Alias phải khác tên collection vật lý. Qdrant hiện đã có collection vật lý
`nmk_chatbot_collection`, vì vậy không thể dùng chính tên này làm alias.

## 1. Chụp trạng thái trước khi thao tác

```powershell
Invoke-RestMethod http://localhost:6333/collections/nmk_chatbot_collection |
  ConvertTo-Json -Depth 10

Invoke-RestMethod http://localhost:6333/aliases |
  ConvertTo-Json -Depth 10

docker top chatbot-api
docker top health-embedding-api
```

Chỉ tiếp tục khi không có process `import_data.py` và Qdrant
`update_queue.length` bằng `0`.

## 2. Tạo collection phiên bản mới

```powershell
docker exec chatbot-api python src/qdrant_collection_admin.py create `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --vector-size 1024
```

Lệnh tạo luôn payload index cho `content_type`, `document_id`,
`corpus_version`, `content_hash`, `source`, `language` và metadata review.

Nếu client timeout nhưng collection đã xuất hiện phía server, không chạy lại
`create` mù. Kiểm tra collection rồi hoàn tất index idempotent:

```powershell
docker exec chatbot-api python src/qdrant_collection_admin.py ensure-indexes `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024
```

## 3. Đưa corpus vào container và dry-run

```powershell
docker cp `
  "data_pipeline/dataset/processed/embedding_documents.jsonl" `
  "chatbot-api:/tmp/embedding_documents.jsonl"

docker exec chatbot-api python src/import_data.py `
  --data-file /tmp/embedding_documents.jsonl `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --dry-run
```

Dry-run hiện tại phải trả `processed_docs=5345`, `total_chunks=23608` và
`error_count=0`. Baseline ngày 30/07/2026 có checksum
`1a474bf5562b8b571eb301f41517d0d2a7739d0e61ef6998fe903365c8665eea`.
Nếu checksum hoặc số chunk thay đổi, coi đó là corpus version mới; không dùng
lại benchmark cũ.

## 4. Import thật và ghi manifest

```powershell
docker exec chatbot-api python src/import_data.py `
  --data-file /tmp/embedding_documents.jsonl `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --skip-collection-create `
  --corpus-version 2026-07-30-v2 `
  --embedding-batch-size 8 `
  --batch-size 50 `
  --manifest-file /usr/src/app/artifacts/imports/2026-07-30-v2.json
```

Importer dùng UUID ổn định nên có thể upsert lại mà không tạo point trùng.
Nếu `fatal_error` xuất hiện, importer dừng thay vì tiếp tục báo tiến độ giả.

Để tiếp tục sau lỗi hạ tầng, đọc `last_successful_upsert_line` trong manifest
và chạy lại với dòng kế tiếp:

```powershell
docker exec chatbot-api python src/import_data.py `
  --data-file /tmp/embedding_documents.jsonl `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --skip-collection-create `
  --corpus-version 2026-07-30-v2 `
  --start-line 1201 `
  --embedding-batch-size 8 `
  --batch-size 50 `
  --manifest-file /usr/src/app/artifacts/imports/2026-07-30-v2-resume.json
```

`1201` chỉ là ví dụ. Không tự suy ra số này nếu manifest chưa xác nhận batch
trước đã upsert thành công. Nếu manifest có validation/embedding error, sửa lỗi
và chạy lại từ đầu vì collection mới dùng stable ID.

## 5. Gate trước khi chuyển alias

```powershell
docker exec chatbot-api python src/qdrant_collection_admin.py verify `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --expected-points 23608 `
  --expected-vector-size 1024
```

Ngoài point count, phải kiểm tra:

- manifest có `status=true`, `error_count=0`;
- `data_file_sha256` khớp giữa dry-run/import;
- `payload_indexes` không rỗng;
- sample search đúng cho InBody, nutrition, exercise và medical safety;
- benchmark retrieval đạt gate trước khi đổi runtime.

Không chuyển alias chỉ vì collection có trạng thái `green`.

## 6. Chuyển alias nguyên tử

```powershell
docker exec chatbot-api python src/qdrant_collection_admin.py activate-alias `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --alias nmk_chatbot_active `
  --expected-points 23608
```

Sau đó đặt trong `backend/.env`:

```dotenv
QDRANT_COLLECTION_NAME=nmk_chatbot_active
QDRANT_COLLECTION_ALIAS=nmk_chatbot_active
CORPUS_VERSION=2026-07-30-v2
```

Recreate riêng API/worker rồi test HTTP thật. Không cần restart Qdrant.

## 7. Rollback

Rollback chỉ thực hiện được khi collection phiên bản trước còn tồn tại. Snapshot
cũ `nmk_chatbot_collection` (13.379 point) đã được xóa sau lần chuyển v2 ngày
07/08/2026 theo yêu cầu vận hành; nếu cần rollback, phải khôi phục từ backup hoặc
import lại một collection đã kiểm định rồi mới chuyển alias.

## Giới hạn còn tồn tại

Importer không khởi tạo BM25 vì index BM25 hiện nằm trong RAM của process và sẽ
mất ngay khi CLI thoát. Vì vậy `bm25_index_persisted=false` là chủ đích. Chưa
được gọi hệ thống là hybrid đầy đủ cho tới khi sparse index được chuyển sang
storage dùng chung và bền vững.

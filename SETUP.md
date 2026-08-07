# Hướng dẫn chạy Health/InBody Multi-Agent RAG MVP

Tài liệu này chạy dự án bằng Docker Desktop trên Windows/PowerShell. Thứ tự khởi động rất quan trọng: **backend trước**, rồi mới đến frontend, vì frontend dùng Docker network do backend tạo.

## 1. Điều kiện cần

- Docker Desktop đang chạy; kiểm tra bằng `docker compose version`.
- PowerShell mở tại thư mục gốc dự án (`LLL RAG`).
- Nếu cần câu trả lời sinh bởi LLM, chuẩn bị Ollama hoặc OpenAI API key.
- Nếu cần RAG vector đầy đủ, chuẩn bị model BGE-M3 (mục 3). Không có model này, các health tool vẫn chạy nhưng không có vector retrieval.

## 2. Cấu hình backend

Tạo file cấu hình từ mẫu, chỉ làm một lần:

```powershell
Copy-Item backend\.env.example backend\.env
```

Mở `backend\.env` và chọn một trong các cấu hình LLM sau:

```env
# Chạy demo không có LLM: API vẫn hoạt động, dùng fallback response.
LLM_PROVIDER=none
```

```env
# Dùng Ollama chạy trên máy host.
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:3b
```

```env
# Dùng OpenAI.
LLM_PROVIDER=openai
OPENAI_API_KEY=<api-key-cua-ban>
OPENAI_MODEL=gpt-4o-mini
```

Nếu **không** chạy embedding service, đặt rõ biến sau để backend không thử gọi service chưa tồn tại:

```env
CUSTOM_EMBEDDING_ENABLED=false
```

> Không commit `backend\.env`, vì file này có thể chứa API key.

## 3. Tùy chọn: chạy embedding BGE-M3 cho RAG vector

Bỏ qua mục này nếu chỉ cần demo health tools, các agent và giao diện chat.

Tải model một lần. Lệnh này cần Python cùng các dependency của `embed_serving` và kết nối Internet:

```powershell
cd embed_serving
Copy-Item .env.serving.template .env.serving
pip install -r requirements_serving.txt
python scripts\download_model_from_spaces.py
```

Sau khi model xuất hiện tại `embed_serving\models\bge-m3`, bật embedding trong `backend\.env`:

```env
CUSTOM_EMBEDDING_ENABLED=true
CUSTOM_EMBEDDING_API_URL=http://host.docker.internal:5001
```

Khởi động embedding service:

```powershell
docker compose -f docker-compose.serving.yml up --build -d
Invoke-WebRequest http://localhost:5001/health
cd ..
```

CPU la cau hinh mac dinh. Chi dung GPU override sau khi CUDA smoke test thanh
cong:

```powershell
docker compose -f docker-compose.serving.yml -f docker-compose.gpu.yml up --build -d
```

## 4. Khởi động backend

```powershell
cd backend
docker compose up --build -d
```

Lệnh này khởi động năm container: `chatbot-api`, `chatbot-worker`, `postgres-db`, `valkey-db`, và `qdrant-db`.

Kiểm tra API:

```powershell
Invoke-WebRequest http://localhost:8000/health
```

Nếu API chưa sẵn sàng, xem log:

```powershell
docker compose logs -f chatbot-api
```

Khi API đã chạy, trang Swagger ở `http://localhost:8000/docs`.

## 5. Khởi động frontend

Mở một PowerShell khác, quay lại thư mục gốc rồi chạy:

```powershell
cd frontend
docker compose up --build -d
```

Mở giao diện tại `http://localhost:8051`.

## 6. Kiểm tra nhanh multi-agent

Trong giao diện, thử câu hỏi:

```text
Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng 12.
Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi mỗi tuần?
```

Trong phần **Agent trace**, luồng thường sẽ có `SupervisorAgent`, các agent chuyên môn phù hợp, `SafetyAgent` và `ResponseComposerAgent`.

## 7. Index dữ liệu cho RAG

RAG chỉ truy xuất được tài liệu sau khi corpus đã được index. Chuẩn bị corpus (nếu chưa có) tại thư mục gốc:

```powershell
python data_pipeline\utils\build_embedding_dataset.py
```

Sau đó copy file JSONL vào container backend và chạy importer:

```powershell
docker cp data_pipeline\dataset\processed\embedding_documents.jsonl chatbot-api:/tmp/embedding_documents.jsonl
cd backend
docker compose exec chatbot-api python src/pipelines/import_data.py `
  --data-file /tmp/embedding_documents.jsonl `
  --collection nmk_chatbot_collection_v20260730_bge_m3_1024 `
  --corpus-version 2026-07-30-v2 `
  --skip-collection-create `
  --skip-existing-points `
  --manifest-file /usr/src/app/artifacts/imports/2026-07-30-v2-import.json
```

`--skip-existing-points` tai danh sach ID Qdrant mot lan va chi encode chunk
con thieu. Day la cach tiep tuc an toan sau migration vector hoac sau khi import
bi gian doan. Duong dan corpus, collection va `corpus-version` phai khop voi
manifest dry-run cua lan import hien tai.

## 8. Dừng dự án

Dừng frontend:

```powershell
cd frontend
docker compose down
```

Dừng backend:

```powershell
cd backend
docker compose down
```

Dừng embedding service (nếu đã bật):

```powershell
cd embed_serving
docker compose -f docker-compose.serving.yml down
```

Các lệnh `down` ở trên giữ lại Docker volumes. Do đó dữ liệu PostgreSQL và Qdrant không bị xóa.

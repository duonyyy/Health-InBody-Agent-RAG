# Hướng dẫn chạy Health/InBody Multi-Agent RAG MVP

Tài liệu này hướng dẫn chạy toàn bộ dự án bằng Docker Desktop trên Windows/PowerShell. 
Hệ thống được tổ chức theo kiến trúc phân tầng chuẩn Enterprise: **Tầng Hạ tầng (Infra) -> Tầng Ứng dụng Backend -> Tầng Giao diện Frontend**.

---

## 1. Điều kiện cần

- Docker Desktop đang chạy; kiểm tra bằng `docker compose version`.
- PowerShell mở tại thư mục gốc dự án (`LLL RAG`).
- Nếu cần câu trả lời sinh bởi LLM, chuẩn bị Ollama (chạy host/remote) hoặc OpenAI API key.
- Nếu cần RAG vector đầy đủ, chuẩn bị model BGE-M3 (mục 3). Không có model này, các health tool vẫn chạy nhưng không có vector retrieval.

---

## 2. Cấu hình môi trường

Tạo file cấu hình backend từ mẫu (chỉ làm một lần):

```powershell
Copy-Item backend\.env.example backend\.env
```

Mở `backend\.env` và chọn một trong các cấu hình LLM sau:

```env
# Chạy demo không có LLM: API vẫn hoạt động, dùng deterministic fallback response.
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

> **Lưu ý bảo mật:** Không commit `backend\.env`, vì file này có thể chứa API key và secret.

---

## 3. Chuẩn bị model BGE-M3 cho RAG Vector (Tùy chọn)

Bỏ qua mục này nếu chỉ cần demo health tools, logic agent và giao diện chat.

Tải model một lần (cần Python và Internet):

```powershell
cd infra\embed_serving
Copy-Item .env.serving.template .env.serving
pip install -r requirements_serving.txt
python scripts\download_model_from_spaces.py
cd ..\..
```

Sau khi model xuất hiện tại `infra\embed_serving\models\bge-m3`, bật embedding trong `backend\.env`:

```env
CUSTOM_EMBEDDING_ENABLED=true
CUSTOM_EMBEDDING_API_URL=http://embedding-api:5000
```

---

## 4. Khởi động Tầng Hạ Tầng (Infra Stack)

Cụm hạ tầng gồm 4 dịch vụ nền tảng: PostgreSQL (Database), Qdrant (Vector DB), Valkey (Cache & Message Broker), và BGE-M3 (Embedding API).

```powershell
docker compose -f infra/docker-compose.infra.yml up --build -d
```

Kiểm tra trạng thái hạ tầng:
```powershell
Invoke-WebRequest http://localhost:5001/health   # Embedding API
Invoke-WebRequest http://localhost:6333/healthz  # Qdrant Vector DB
```

---

## 5. Khởi động Tầng Ứng Dụng Backend

Cụm ứng dụng backend gồm 3 dịch vụ: `chatbot-api` (FastAPI), `chatbot-worker` (Celery Worker), và `chatbot-scheduler` (Celery Beat).

```powershell
docker compose -f backend/docker-compose.yml up --build -d
```

Kiểm tra API:
```powershell
Invoke-WebRequest http://localhost:8000/health
```

Trang tài liệu Swagger UI có tại: `http://localhost:8000/docs`.

Xem nhật ký nếu cần debug:
```powershell
docker compose -f backend/docker-compose.yml logs -f chatbot-api
```

---

## 6. Khởi động Tầng Giao Diện Frontend

```powershell
docker compose -f frontend/docker-compose.yml up --build -d
```

Mở giao diện người dùng tại trình duyệt: `http://localhost:8051`.

---

## 7. Kiểm tra nhanh Multi-Agent

Trong giao diện Streamlit, gửi câu hỏi thử nghiệm:

```text
Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng 12.
Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi mỗi tuần?
```

Trong phần **Agent trace**, luồng thực thi sẽ hiển thị lần lượt: `SupervisorAgent`, `InBodyAgent`, `NutritionAgent`/`TrainingAgent`, `SafetyAgent` và `ResponseComposerAgent`.

---

## 8. Dừng dự án

Khi cần tắt hệ thống:

```powershell
# 1. Dừng frontend
docker compose -f frontend/docker-compose.yml down

# 2. Dừng backend
docker compose -f backend/docker-compose.yml down

# 3. Dừng hạ tầng (dữ liệu PostgreSQL, Qdrant và Valkey vẫn được lưu giữ an toàn trong volumes)
docker compose -f infra/docker-compose.infra.yml down
```

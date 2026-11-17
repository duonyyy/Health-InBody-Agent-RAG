# Hướng dẫn chạy Health/InBody Multi-Agent RAG MVP

Tài liệu này hướng dẫn backend gộp, hạ tầng và frontend trên Windows/PowerShell. Đây là cấu hình local có xác thực; không phải chứng nhận production-ready. Các lệnh bên dưới chạy tại repo root.

---

## 1. Điều kiện cần

- Docker Desktop đang chạy; kiểm tra cả `docker version` và `docker compose version`. Compose config hợp lệ chưa chứng minh Docker Engine hoạt động.
- PowerShell mở tại thư mục gốc dự án (`LLL RAG`).
- Nếu cần câu trả lời sinh bởi LLM, chuẩn bị Ollama (chạy host/remote) hoặc OpenAI API key.
- Nếu cần RAG vector đầy đủ, chuẩn bị model BGE-M3 (mục 3). Không có model này, các health tool vẫn chạy nhưng không có vector retrieval.

---

## 2. Cấu hình môi trường

### Cài mới, chưa có database/volume cũ

Đoạn lệnh sau tạo backend/.env từ template, sinh hai secret độc lập có ít nhất 32 byte entropy và không in giá trị ra console. Cần Python 3.10+. Lệnh từ chối ghi đè file đã có; **không dùng để đổi credential của PostgreSQL volume hiện hữu**.

```powershell
@'
from pathlib import Path
import re
import secrets

target = Path("backend/.env")
if target.exists():
    raise SystemExit("backend/.env đã tồn tại; giữ credential hiện có và chỉnh trong editor.")
db_password = secrets.token_hex(32)
values = {
    "POSTGRES_PASSWORD": db_password,
    "DATABASE_URL": "postgresql+psycopg2://health_user:" + db_password + "@postgres-db:5432/health_inbody",
    "JWT_SIGNING_KEY": secrets.token_hex(32),
}
text = Path("backend/.env.example").read_text(encoding="utf-8")
for name, value in values.items():
    text, count = re.subn(r"^" + name + r"=.*$", lambda _: name + "=" + value, text, flags=re.M)
    if count != 1:
        raise SystemExit("Template không đúng cấu trúc; chưa tạo file cấu hình.")
with target.open("x", encoding="utf-8") as stream:
    stream.write(text)
'@ | python -B -

if (-not (Test-Path frontend/.env)) {
    Copy-Item frontend/.env.example frontend/.env
}
```

### Đã có backend/.env hoặc PostgreSQL volume

Giữ POSTGRES_USER/POSTGRES_DB/POSTGRES_PASSWORD và tên volume đang dùng; DATABASE_URL phải khớp credential thực trong database. `POSTGRES_PASSWORD` trong Compose chỉ khởi tạo role khi volume mới, không đổi password của role trong volume cũ. Không xóa/reset volume để giải quyết lỗi đăng nhập; nếu cần rotation thì backup, inventory mọi client và làm một đợt riêng.

Bổ sung trường thiếu trong editor theo backend/.env.example. JWT_SIGNING_KEY phải ngẫu nhiên, tối thiểu 32 byte; có thể dùng `secrets.token_hex(32)` để tạo và ghi trực tiếp vào file local mà không in/log. Không thay một signing key đang phục vụ chỉ để chạy hướng dẫn này, vì token cũ sẽ không còn hợp lệ.

### Auth và CORS

- Mặc định backend `AUTH_MODE=production`, frontend `NEXT_PUBLIC_AUTH_MODE=production`: đăng ký/đăng nhập qua `/auth/register`, `/auth/login`, token JWT HS256 có hạn 900 giây. Đây là first-party auth; không cần IdP/JWKS ngoài.
- `JWT_ISSUER=bodywise-local`, `JWT_AUDIENCE=bodywise-web` là định danh của ứng dụng, không phải URL nhà cung cấp. Thiếu issuer/audience hoặc key đủ dài thì production từ chối token; không bật development để vượt lỗi cấu hình.
- `CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000` dành cho browser local. Dùng origin đầy đủ scheme/host/port, không path, không wildcard. Với LAN/HTTPS phải thay bằng frontend origin thực; domain API có thể khác origin frontend.
- Chế độ local development chỉ chọn tường minh ở **cả hai file**: backend `AUTH_MODE=development`, frontend `NEXT_PUBLIC_AUTH_MODE=development`. Header X-Dev-User-Id chỉ có tác dụng ở chế độ này; phải rebuild frontend khi đổi mode.
- POSTGRES_PASSWORD và DATABASE_URL trong template cố ý để trống. Password tự chọn có ký tự đặc biệt phải được URL-encode trong DATABASE_URL; giá trị `.env` có `$` cần quote đúng để tránh nội suy ngoài ý muốn. Script cài mới dùng hex để tránh hai vấn đề này.

### LLM và embedding

Mở backend/.env và chọn provider/model sẵn có:

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

> Giữ mọi secret trong file local không track. NEXT_PUBLIC_* là dữ liệu công khai; không đặt JWT signing key, password hoặc provider key vào frontend/.env/build args.

### Hai giai đoạn đọc env của Compose

Các lệnh từ repo root luôn dùng `--env-file backend/.env` cho infra/backend và `--env-file frontend/.env` cho UI. CLI `--env-file` cấp giá trị cho `${...}`; service `env_file` cấp biến vào container. `environment` tường minh và biến PowerShell cùng tên có thể ghi đè giá trị trong file. Kiểm tra AUTH_MODE/LLM_PROVIDER/DATABASE_URL của shell trước chạy, không in secret hoặc toàn bộ `compose config`. Xác thực bằng `config --quiet`.

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
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml config --quiet
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml up -d postgres-db qdrant-db valkey-db
# Chỉ khi đã chuẩn bị BGE-M3:
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml up --build -d embedding-api
```

Kiểm tra trạng thái hạ tầng:
```powershell
Invoke-WebRequest http://localhost:5001/health   # Embedding API
Invoke-WebRequest http://localhost:6333/healthz  # Qdrant Vector DB
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml exec -T postgres-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1"'
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml exec -T valkey-db valkey-cli ping
```

Cổng PostgreSQL 5432, Qdrant 6333/6334, Valkey 6379 và embedding 5001 mặc định chỉ bind 127.0.0.1 trên host. API/worker vẫn gọi qua postgres-db:5432, qdrant-db:6333, valkey-db:6379 và embedding-api:5000 trong internal-network. Không đổi endpoint container thành localhost. Loopback không bổ sung auth Qdrant/Valkey hay xác nhận an toàn cho shared production; xem [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/) và kiểm tra phiên bản Engine/firewall khi triển khai.

Volume mới dùng infra/database/init.sql. Database cũ phải kiểm tra schema_migrations và áp dụng migration được review, gồm `20261105_03_first_party_auth`, trước nghiệm thu login; không thay bằng create_all và không chạy migration vào DB thật trong hotfix cấu hình.

---

## 5. Khởi động Tầng Ứng Dụng Backend

Cụm ứng dụng backend gồm 3 dịch vụ: `chatbot-api` (FastAPI), `chatbot-worker` (Celery Worker), và `chatbot-scheduler` (Celery Beat).

```powershell
docker compose --env-file backend/.env -f backend/docker-compose.yml config --quiet
docker compose --env-file backend/.env -f backend/docker-compose.yml up --build -d
```

Kiểm tra API:
```powershell
Invoke-WebRequest http://localhost:8000/health
Invoke-WebRequest http://localhost:8000/health/ready
```

Trang tài liệu Swagger UI có tại: `http://localhost:8000/docs`.

Xem nhật ký nếu cần debug:
```powershell
docker compose --env-file backend/.env -f backend/docker-compose.yml logs -f chatbot-api
```

---

## 6. Khởi động Tầng Giao Diện Frontend (Next.js)

### Cách 1: Chạy bằng Docker Compose
```powershell
docker compose --env-file frontend/.env -f frontend/docker-compose.yml config --quiet
docker compose --env-file frontend/.env -f frontend/docker-compose.yml up --build -d
```
Mở giao diện người dùng tại trình duyệt: `http://localhost:3000`.

NEXT_PUBLIC_API_URL mặc định là `http://localhost:8000`, URL mà **browser** gọi. Không dùng `http://chatbot-api:8000`, vì đó là DNS Docker. Nếu mở UI từ máy khác, đặt hostname/IP API mà máy đó truy cập được, thêm origin UI vào CORS backend và rebuild UI. NEXT_PUBLIC_* được đóng vào bundle lúc build; đổi env khi container start không sửa được bundle. Tham khảo [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser).

### Cách 2: Chạy trực tiếp qua Node.js (phát triển)
```powershell
cd frontend
npm ci
npm run dev
```
Giao diện sẽ chạy tại `http://localhost:3000`.

---

## 7. Kiểm tra nhanh Multi-Agent

Trong giao diện Web, gửi câu hỏi thử nghiệm:

```text
Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng 12.
Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi mỗi tuần?
```

Đăng ký/đăng nhập trước khi nhập dữ liệu cá nhân. Login phụ thuộc PostgreSQL schema và rate limiter Valkey thật; lỗi dependency trả 503, không chuyển sang dữ liệu mẫu. Frontend production giữ access token trong RAM; tải lại trang cần đăng nhập lại.

Ba specialist công khai là InBodyAgent, LifestyleAgent và KnowledgeAgent. ContextLoader, IntentRouter, SafetyGuard, AnswerComposer là workflow stages; nutrition/training/RAG/web/general chat là capability nội bộ. Deterministic urgent precheck đứng trước DB/queue/LLM/retrieval; lời chào/BMI low-risk đủ dữ liệu đi fast-path.

Lệnh kiểm tra syntax hiện hành:

```powershell
python -m py_compile backend/src/api/app.py backend/src/agents/graph.py backend/src/llm/client.py backend/src/jobs/tasks.py
```

Trước mọi restart/deploy khi hệ thống đã có dữ liệu: ghi collection/alias/count, job import và manifest/log cuối theo AGENTS.md. Nếu job chưa rõ hoặc Engine không truy cập được, dừng deploy. Config hợp lệ, build đạt hoặc vài HTTP smoke chưa chứng minh chất lượng corpus, provider hay toàn bộ hệ thống.

---

## 8. Dừng dự án

Khi cần tắt hệ thống:

```powershell
# 1. Dừng frontend
docker compose --env-file frontend/.env -f frontend/docker-compose.yml down

# 2. Dừng backend
docker compose --env-file backend/.env -f backend/docker-compose.yml down

# 3. Dừng hạ tầng (dữ liệu PostgreSQL, Qdrant và Valkey vẫn được lưu giữ an toàn trong volumes)
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml down
```

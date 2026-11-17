# Infrastructure Plane — Health/InBody Agent RAG

Thư mục `infra/` đóng gói toàn bộ hạ tầng kỹ thuật (Data Stores, Vector Database, Cache/Queue Broker, Embedding Serving, LLM Runtime và Monitoring/Observability) phục vụ cho hệ thống **Health/InBody Multi-Agent RAG**.

Theo chuẩn kiến trúc Enterprise AI Monorepo, tầng hạ tầng được tách biệt hoàn toàn khỏi tầng ứng dụng (`backend/`, `frontend/`, `ocr-services/`) để đảm bảo:
1. **Cô lập vòng đời (Lifecycle Isolation):** Rebuild hoặc restart backend/frontend không làm ảnh hưởng đến dữ liệu đang chạy trong Database, Vector Store và Cache.
2. **Khởi tạo một chạm (Single Command Bootstrap):** Chỉ cần một lệnh compose duy nhất để dựng toàn bộ hạ tầng nền tảng.
3. **Mạng nội bộ đồng nhất (`internal-network`):** Các container dùng service DNS trong bridge network; mạng này không thay thế xác thực hoặc firewall của shared deployment.

---

## 1. Sơ đồ các thành phần hạ tầng

```text
infra/
├── docker-compose.infra.yml          # Cụm hạ tầng lõi (Postgres, Qdrant, Valkey, BGE-M3)
├── (env dùng chung: ../backend/.env)  # POSTGRES_* và volume names, xem SETUP.md
│
├── database/                         # [RDBMS] PostgreSQL 16 (Users, Personalization, Memory)
│   ├── init.sql                      # DDL cài mới (12 bảng nghiệp vụ + ledger)
│   ├── README.md                     # Tài liệu quan hệ dữ liệu & migration
│   └── migrations/                   # Các script migration up/down theo version
│
├── qdrant/                           # [Vector DB] Qdrant Engine (1024-dim BGE-M3 embeddings)
│   ├── production.yaml               # Cấu hình log và runtime Qdrant
│   └── README.md                     # Nguyên tắc alias blue/green & idempotent import
│
├── valkey/                           # [Cache & Message Broker] Valkey (Redis-compatible)
│   ├── valkey.conf                   # Cấu hình RDB/AOF persistence & LRU memory
│   └── README.md                     # Vai trò cache phản hồi & Celery broker
│
├── embed_serving/                    # [Microservice] BGE-M3 Vector Embedding API
│   ├── Dockerfile.cpu-serving        # Image tối ưu CPU (PyTorch CPU, batch 8)
│   ├── Dockerfile.gpu-serving        # Image tối ưu CUDA (float16, batch 2, RTX 3050 4GB)
│   ├── docker-compose.serving.yml    # Chạy standalone CPU
│   ├── docker-compose.gpu.yml        # Override GPU
│   ├── scripts/serve_model.py        # REST API (/health, /embed, /similarity)
│   └── README.md
│
├── llm/                              # [LLM Runtime] Mô hình ngôn ngữ lớn
│   ├── docker-compose.ollama.yml     # Container hóa Ollama cục bộ (tùy chọn)
│   ├── remote-llm-server-using-kaggle-gpu-ollama.ipynb # Remote T4 Ollama qua Cloudflare Tunnel
│   └── README.md
│
└── monitoring/                       # [Observability] Giám sát & Truy vết phân tán
    ├── docker-compose.monitoring.yml # Langfuse self-hosted stack (Postgres + Langfuse server)
    └── README.md                     # Hướng dẫn Langfuse Cloud vs Self-hosted
```

---

## 2. Thông số cổng mạng & Dịch vụ

| Dịch vụ | Tên container | Image | Port nội bộ | Port host | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL** | `postgres-db` | `postgres:16-alpine` | `5432` | `127.0.0.1:5432` | Dữ liệu người dùng, chỉ số đo, lịch sử chat |
| **Qdrant** | `qdrant-db` | `qdrant/qdrant:latest` | `6333`, `6334` | `127.0.0.1:6333`, `127.0.0.1:6334` | Vector collection RAG |
| **Valkey** | `valkey-db` | `valkey/valkey:bookworm` | `6379` | `127.0.0.1:6379` | Response cache & Celery broker |
| **Embedding API** | `health-embedding-api` | `nmk-health-embedding:cpu` | `5000` | `127.0.0.1:5001` | Sinh vector ngữ nghĩa BGE-M3 (1024 chiều) |
| **Ollama** *(tùy chọn)* | `ollama-service` | `ollama/ollama:latest` | `11434` | `11434` | Chạy LLM local khi bật compose riêng |
| **Langfuse** *(tùy chọn)*| `langfuse-server` | `langfuse/langfuse:2` | `3000` | `3000` | Giao diện giám sát LLM trace & token |

---

## 3. Hướng dẫn vận hành

Theo [SETUP.md](../SETUP.md), tạo hoặc bổ sung backend/.env, giữ credential của volume cũ. Dùng duy nhất file đó cho infra/backend để POSTGRES_* và DATABASE_URL không lệch nhau. POSTGRES_PASSWORD bắt buộc, không còn fallback password cố định. CLI --env-file dùng cho nội suy; environment của shell có thể ghi đè nó. Không xuất compose config đầy đủ ra report/log.

Postgres/Qdrant/Valkey/embedding host port trong stack chính và standalone embedding bind 127.0.0.1. Container vẫn gọi postgres-db:5432, qdrant-db:6333, valkey-db:6379, embedding-api:5000. Kiểm tra runtime binding bằng compose port/inspect sau triển khai; config hợp lệ chưa chứng minh port thực. Không tự thêm auth Qdrant/Valkey hoặc đổi role password trên volume cũ trong hotfix này. Stack monitoring/Ollama tùy chọn không thuộc thay đổi bind của stack chính và cần review riêng trước khi public.

### Khởi động cụm hạ tầng chính
```powershell
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml config --quiet
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml up -d postgres-db qdrant-db valkey-db
# Chỉ khi model BGE-M3 đã chuẩn bị:
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml up --build -d embedding-api
```

### Kiểm tra sức khỏe các dịch vụ
```powershell
Invoke-WebRequest http://localhost:5001/health   # Embedding API: model_loaded=true
Invoke-WebRequest http://localhost:6333/healthz  # Qdrant: ok
```

### Tùy chọn: Chạy thêm mô hình nhúng trên GPU (NVIDIA CUDA)
```powershell
docker compose `
  --env-file backend/.env `
  -f infra/docker-compose.infra.yml `
  -f infra/embed_serving/docker-compose.gpu.yml `
  up -d
```

### Tùy chọn: Chạy Langfuse Self-Hosted để giám sát
```powershell
docker compose -f infra/monitoring/docker-compose.monitoring.yml up -d
```
Truy cập `http://localhost:3000` để xem Dashboard.

### Tắt cụm hạ tầng
```powershell
docker compose --env-file backend/.env -f infra/docker-compose.infra.yml down
```
> Lệnh `down` giải phóng các container và mạng `internal-network`, các Docker named volume (`postgres_data`, `qdrant_volume`, `valkey_data`) được giữ nguyên, bảo toàn toàn bộ dữ liệu.

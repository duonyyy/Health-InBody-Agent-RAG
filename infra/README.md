# Infrastructure Plane — Health/InBody Agent RAG

Thư mục `infra/` đóng gói toàn bộ hạ tầng kỹ thuật (Data Stores, Vector Database, Cache/Queue Broker, Embedding Serving, LLM Runtime và Monitoring/Observability) phục vụ cho hệ thống **Health/InBody Multi-Agent RAG**.

Theo chuẩn kiến trúc Enterprise AI Monorepo, tầng hạ tầng được tách biệt hoàn toàn khỏi tầng ứng dụng (`backend/`, `frontend/`, `ocr-services/`) để đảm bảo:
1. **Cô lập vòng đời (Lifecycle Isolation):** Rebuild hoặc restart backend/frontend không làm ảnh hưởng đến dữ liệu đang chạy trong Database, Vector Store và Cache.
2. **Khởi tạo một chạm (Single Command Bootstrap):** Chỉ cần một lệnh compose duy nhất để dựng toàn bộ hạ tầng nền tảng.
3. **Mạng nội bộ đồng nhất (`internal-network`):** Tất cả dịch vụ giao tiếp bảo mật trong mạng bridge nội bộ của Docker.

---

## 1. Sơ đồ các thành phần hạ tầng

```text
infra/
├── docker-compose.infra.yml          # Cụm hạ tầng lõi (Postgres, Qdrant, Valkey, BGE-M3)
├── .env.infra.example                # Mẫu biến môi trường cho hạ tầng
├── .env.infra                        # Biến môi trường đang áp dụng
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
| **PostgreSQL** | `postgres-db` | `postgres:16-alpine` | `5432` | `5432` | Dữ liệu người dùng, chỉ số đo, lịch sử chat |
| **Qdrant** | `qdrant-db` | `qdrant/qdrant:latest` | `6333`, `6334` | `6333`, `6334` | Vector collection RAG |
| **Valkey** | `valkey-db` | `valkey/valkey:bookworm` | `6379` | `6379` | Response cache & Celery broker |
| **Embedding API** | `health-embedding-api` | `nmk-health-embedding:cpu` | `5000` | `5001` | Sinh vector ngữ nghĩa BGE-M3 (1024 chiều) |
| **Ollama** *(tùy chọn)* | `ollama-service` | `ollama/ollama:latest` | `11434` | `11434` | Chạy LLM local khi bật compose riêng |
| **Langfuse** *(tùy chọn)*| `langfuse-server` | `langfuse/langfuse:2` | `3000` | `3000` | Giao diện giám sát LLM trace & token |

---

## 3. Hướng dẫn vận hành

### Khởi động cụm hạ tầng chính
```powershell
docker compose -f infra/docker-compose.infra.yml up -d
```

### Kiểm tra sức khỏe các dịch vụ
```powershell
Invoke-WebRequest http://localhost:5001/health   # Embedding API: model_loaded=true
Invoke-WebRequest http://localhost:6333/healthz  # Qdrant: ok
```

### Tùy chọn: Chạy thêm mô hình nhúng trên GPU (NVIDIA CUDA)
```powershell
docker compose `
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
docker compose -f infra/docker-compose.infra.yml down
```
> Lệnh `down` giải phóng các container và mạng `internal-network`, các Docker named volume (`postgres_data`, `qdrant_volume`, `valkey_data`) được giữ nguyên, bảo toàn toàn bộ dữ liệu.

# Báo cáo Baseline WP-00: Hiện trạng hệ thống & Deployment Profile

> **Bằng chứng lịch sử:** Profile B đã được rút ngày 2026-11-05. Không dùng báo cáo này làm cấu hình hay runbook hiện hành; kế hoạch active là `docs/KE_HOACH_NANG_CAP_DU_AN_2026.md` phiên bản 3.0 (backend gộp).

**Ngày thực hiện:** 2026-11-04  
**Git HEAD:** `8d0ae8cc4eff0f65ef770c3abc56063e999d5895`  
**Git Status:**
- `M docs/KE_HOACH_NANG_CAP_DU_AN_2026.md`
- `D docs/P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md`
- `D docs/P1_PERSONALIZATION_REPORT.md`
- `.codegraph`: Không tồn tại (`False`).

---

## 1. Kiểm kê Deployment Profile

### Profile A: Monolith Backend
- **Compose file:** `backend/docker-compose.yml`
- **Entrypoint:** `uvicorn api.app:app --host 0.0.0.0 --port 8000`
- **Các thành phần:** `chatbot-api` (port 8000), `chatbot-worker` (Celery worker), `chatbot-scheduler` (Celery beat).
- **Trạng thái:** Compatibility baseline được bảo vệ theo tài liệu SETUP.

### Profile B: Tách Microservices (Core-API & Agent-Service)
- **Compose file:** `docker-compose.microservices.yml`
- **Thành phần 1 - Core Business API (BFF):**
  - Context build: `./core-api`, Dockerfile: `core-api/Dockerfile`
  - Cổng host: 8000
  - Entrypoint: `uvicorn main:app --host 0.0.0.0 --port 8000`
  - Trách nhiệm: Quản lý Auth, Consent, PostgreSQL (Profile, Measurements, Conversations), BFF gọi sang `agent-service`.
- **Thành phần 2 - Agentic AI Platform (Agent-Service):**
  - Context build: `./agent-service`, Dockerfile: `agent-service/Dockerfile`
  - Cổng host: 8001
  - Entrypoint: `uvicorn main:app --host 0.0.0.0 --port 8001`
  - Trách nhiệm: Multi-agent reasoning (LangGraph), Tools, RAG retrieval (Qdrant), LLM.

### Hạ tầng và Frontend
- **Hạ tầng:** `infra/docker-compose.infra.yml` (PostgreSQL 5432, Qdrant 6333/6334, Valkey 6379).
- **Embedding:** `infra/embed_serving/docker-compose.serving.yml` (bge-m3 serving port 5000).
- **Frontend:** `frontend/docker-compose.yml` (Next.js 16 port 3000).

---

## 2. Kiểm tra Runtime và Dependency (Read-Only)

- **Docker Daemon:** `OFFLINE` / `UNAVAILABLE` (`open //./pipe/docker_engine: The system cannot find the file specified`).
- **Network Listeners:** Không có process nào đang lắng nghe trên các cổng 8000, 8001, 3000, 5432, 6333, 6334, 6379, 8080.
- **Đánh giá Runtime:** Toàn bộ runtime containers/processes hiện đang `UNAVAILABLE` do môi trường (Docker daemon chưa chạy trên host). Không có tiến trình nào bị xung đột cổng tại thời điểm kiểm tra.

---

## 3. Cú pháp và Compose Validation

1. **AST Syntax Check:**
   - `backend/src/api/app.py`: `OK`
   - `backend/src/agents/graph.py`: `OK`
   - `core-api/src/main.py`: `OK`
   - `agent-service/src/main.py`: `OK`
2. **Docker Compose Config Schema Validation:**
   - `infra/docker-compose.infra.yml`: `OK` (exit code 0)
   - `backend/docker-compose.yml`: `OK` (exit code 0)
   - `docker-compose.microservices.yml`: `OK` (exit code 0)
   - `infra/embed_serving/docker-compose.serving.yml`: `OK` (exit code 0)
   - `frontend/docker-compose.yml`: `OK` (exit code 0)

---

## 4. Kết quả Test Baseline trên Host (Python 3.13)

| Test Suite | Số lượng test | Thời gian | Kết quả | Ghi chú |
|---|---|---|---|---|
| Backend Unit & Data Pipeline Selection | 34 | 9.94s | **34 passed** | Chạy với PYTHONPATH `backend/src` + root |
| Core-API Unit Tests | 4 | 5.24s | **4 passed** | Chạy với PYTHONPATH `core-api/src` + root |
| Agent-Service Unit Tests | 5 | 4.64s | **5 passed** | Chạy với PYTHONPATH `agent-service/src` + root |

*Lưu ý:* Cả `core-api/tests` và `agent-service/tests` hiện pass trên host vì được cấp root vào PYTHONPATH để import `contracts`. Trong Docker build sạch, các test này sẽ fail do thiếu contracts và dependencies chưa đồng bộ.

---

## 5. Danh mục rủi ro đóng gói được xác nhận cho WP-01

1. **Build context của Core-API và Agent-Service:** Cả hai Dockerfile chỉ nhận context con (`./core-api` và `./agent-service`) nên không truy cập được thư mục `contracts/` ở root.
2. **Khai báo thiếu dependencies trực tiếp:**
   - `core-api/src/config.py` import `pydantic_settings`, nhưng `core-api/requirements.txt` không có `pydantic-settings`.
   - `core-api/src/api/routes/ocr.py` import `requests`, nhưng `core-api/requirements.txt` không có `requests`.
3. **Cross-module coupling giữa Core-API và Agent-Service:**
   - `core-api/src/persistence/personalization_service.py` import `memory.store` và `memory.context`, nhưng `core-api` chưa có module `memory`.
   - `agent-service/src/memory/models.py` import `persistence.database.Base`, nhưng `agent-service` không có `persistence` (và không nên kết nối DB trực tiếp).


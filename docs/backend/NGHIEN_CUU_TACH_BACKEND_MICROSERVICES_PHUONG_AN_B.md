# BÁO CÁO NGHIÊN CỨU & BẢN THIẾT KẾ KIẾN TRÚC
## PHÂN TÁCH VẬT LÝ BACKEND THÀNH 2 MICROSERVICES: CORE-API VÀ AGENT-SERVICE
**Dự án:** Health / InBody Multi-Agent RAG Platform (KLTN & MWG AI Engineer Portfolio)  
**Tài liệu:** `docs/backend/NGHIEN_CUU_TACH_BACKEND_MICROSERVICES_PHUONG_AN_B.md`  
**Trạng thái:** Architecture Proposal & Migration Feasibility Study (Chuẩn Enterprise 2026)  
**Tham chiếu:** [RetailMind_AI Architecture Blueprint](file:///C:/Users/Admin/Desktop/ExcelMCP/MWG_AI_Engineer_Interview_Study_Kit/RetailMind_AI/docs/REBUILD_BLUEPRINT.md) & [MWG Agentic AI JD Checklist](file:///c:/Users/Admin/Desktop/KLTN/LLL%20RAG/MWG_AI_Engineer_Agentic_AI_JD_Checklist.md)

---

## 1. TỔNG QUAN ĐIỀU HÀNH (EXECUTIVE SUMMARY)

Hiện tại, toàn bộ hệ thống xử lý phía máy chủ của dự án đang chạy chung trong một container duy nhất: `backend/` (tiến trình `chatbot-api` trên Port 8000). Thư mục này đang gánh đồng thời 2 nhóm trách nhiệm hoàn toàn khác nhau:
1. **Nghiệp vụ cốt lõi (Business Domain):** Xác thực người dùng (JWT/Dev context), lưu trữ cơ sở dữ liệu PostgreSQL (hồ sơ `user_profiles`, lịch sử `inbody_measurements`, mục tiêu `health_goals`), điều phối tác vụ nền Celery/Valkey.
2. **Trí tuệ nhân tạo (AI & Agent Platform):** Đồ thị tác tử LangGraph (`supervisor`, `inbody`, `nutrition`, `training`, `rag`, `safety`, `composer`), truy vấn tìm kiếm lai Qdrant Hybrid Search (Dense BGE-M3 + BM25), giao tiếp mô hình LLM (Ollama/OpenAI), và bộ công cụ tính toán sinh trắc.

### Kết luận nghiên cứu khả thi:
* **Khả thi 100%:** Việc phân tách vật lý thành 2 dịch vụ độc lập: **`core-api` (Port 8000)** và **`agent-service` (Port 8001)** là hoàn toàn khả thi và mang lại bước nhảy vọt về chất lượng kiến trúc phần mềm.
* **Tác động đến bài toán tuyển dụng MWG:** Thể hiện trọn vẹn năng lực thiết kế hệ thống phân tán (Distributed Systems), ranh giới bảo mật tác tử (Agent Boundary), và cách ly tải trọng tính toán (Workload Isolation) theo đúng tiêu chuẩn tuyển dụng **Senior AI Engineer (Agentic AI)** của MWG.
* **Chi phí & Thách thức:** Phải thiết lập hợp đồng giao tiếp HTTP/SSE nội bộ giữa 2 service, chia tách cấu hình Docker Compose, và tái cấu trúc test suite.

---

## 2. PHÂN TÍCH HIỆN TRẠNG (AS-IS AUDIT) & ĐIỂM NGHẼN

### 2.1. Cấu trúc hiện tại của `backend/src/`
```text
backend/src/
├── api/             # Gộp chung routes: personalization, inbody_ocr, memory, app.py
├── auth/            # Context xác thực JWT & legacy matching
├── persistence/     # SQLAlchemy models, PostgreSQL connection, personalization service
├── health/          # Công cụ y tế & tính toán chỉ số InBody
├── agents/          # LangGraph multi-agent graph, supervisor, composer, fast-paths
├── rag/             # Qdrant client, dense search, BM25 snapshot, reranker
├── llm/             # Client kết nối Ollama/OpenAI, prompt builder
├── memory/          # SQLite memory, Zep client, conversation store
├── integrations/    # Tavily search, external APIs
└── jobs/            # Celery tasks (index documents, async chat worker)
```

### 2.2. Các điểm nghẽn kiến trúc (Architectural Pain Points)
1. **Rủi ro sập dây chuyền (Blast Radius):** Nếu một truy vấn RAG trên Qdrant bị treo hoặc tiến trình LLM gây nghẽn bộ nhớ VRAM/RAM, tiến trình FastAPI chính bị block. Người dùng không thể đăng nhập, không thể xem biểu đồ lịch sử InBody hay chỉnh sửa mục tiêu cân nặng.
2. **Xung đột tài nguyên phần cứng (GPU 4GB Constraint):** Core API chỉ cần tài nguyên I/O nhẹ (CPU/RAM nhỏ), trong khi Agent Platform cần VRAM cho LLM (Qwen 8B) và BGE-M3 embedding. Việc gộp chung khiến worker của API tranh chấp CPU/RAM với tiến trình inference.
3. **Vi phạm nguyên tắc Ranh giới Tác tử (Agent Boundary Violation):** Hiện tại `agents/` có thể truy cập thẳng vào `persistence/` để đọc dữ liệu thô. Theo chuẩn an toàn dữ liệu cá nhân (Nghị định 13/2023/NĐ-CP), LLM/Agent chỉ được nhận dữ liệu ngữ cảnh đã qua xác thực và che giấu PII (Redacted Context).

---

## 3. THIẾT KẾ KIẾN TRÚC ĐÍCH (TO-BE ARCHITECTURE BLUEPRINT)

### 3.1. Sơ đồ tương tác hệ thống (System Context & Dataflow)

```mermaid
flowchart TD
    subgraph ClientLayer ["TẦNG GIAO DIỆN (CLIENT LAYER)"]
        UI["Frontend Streamlit\n(Port 8501)"]
    end

    subgraph CoreLayer ["TẦNG NGHIỆP VỤ & BẢO MẬT (CORE API SERVICE - PORT 8000)"]
        GW["FastAPI Gateway / BFF"]
        AUTH["Auth & Principal Guard\n(JWT / Dev Header)"]
        SVC_USER["User & InBody Service"]
        SVC_ORCH["Chat Orchestration Client"]
        DB_PG[("PostgreSQL\n(Single Source of Truth)")]
        QUEUE["Celery Task Queue\n(Valkey Cache)"]
    end

    subgraph AgentLayer ["TẦNG TÁC TỬ & RAG (AGENT SERVICE - PORT 8001)"]
        AGENT_API["Agent HTTP / SSE Gateway"]
        GUARD["Safety Pre-check Gate\n(Urgent Fast-Path < 500ms)"]
        GRAPH["LangGraph Orchestrator\n(Supervisor + Specialists)"]
        RAG_CORE["Hybrid Search Engine\n(BM25 + Dense)"]
        HEALTH_TOOLS["Biometric & Medical Tools\n(BMI, PBF, BMR, Training)"]
    end

    subgraph InfraLayer ["HẠ TẦNG CHUYÊN BIỆT (INFRASTRUCTURE)"]
        OCR["OCR Service\n(PaddleOCR - Port 18100)"]
        QDRANT[("Qdrant Vector DB\n(Port 6333)")]
        EMBED["BGE-M3 Serving\n(Port 5000)"]
        LLM_ENG["LLM Engine\n(Ollama Qwen / OpenAI)"]
    end

    %% Client Interactions
    UI -->|"HTTP REST & SSE\n(Port 8000)"| GW

    %% Core API Internal Flow
    GW --> AUTH
    AUTH --> SVC_USER
    SVC_USER <--> DB_PG
    GW --> SVC_ORCH
    SVC_ORCH --> QUEUE
    SVC_USER -->|"HTTP POST /ocr/inbody"| OCR

    %% Inter-Service Communication (Core -> Agent)
    SVC_ORCH -->|"POST /v1/agent/chat\n(Kèm Authenticated Principal & InBody Context)"| AGENT_API

    %% Agent Internal Flow
    AGENT_API --> GUARD
    GUARD -->|"Urgent: Fast-Path Exit"| AGENT_API
    GUARD -->|"Safe: Tiếp tục xử lý"| GRAPH
    GRAPH <--> HEALTH_TOOLS
    GRAPH <--> RAG_CORE
    GRAPH <-->|"Suy luận & Function Calling"| LLM_ENG

    %% Agent External Services
    RAG_CORE <--> QDRANT
    RAG_CORE <--> EMBED
```

---

## 4. MA TRẬN BÓC TÁCH TRÁCH NHIỆM & PHÂN BỔ MÃ NGUỒN

### 4.1. Bảng phân định 2 Service

| Tiêu chí | `core-api` (Port 8000) | `agent-service` (Port 8001) |
| :--- | :--- | :--- |
| **Bản chất dịch vụ** | State-heavy, ACID, CRUD, Bảo mật dữ liệu người dùng | Compute-heavy, Stateless Agent Reasoning, RAG & LLM |
| **Công nghệ** | FastAPI, SQLAlchemy, Alembic, PostgreSQL, Celery | FastAPI, LangGraph, Qdrant Client, httpx, Ollama/OpenAI |
| **Các nhóm Endpoint** | • `/me/profile` (Xem/sửa hồ sơ)<br>• `/me/measurements` (CRUD lịch sử InBody)<br>• `/me/goals` (Mục tiêu cân nặng/mỡ)<br>• `/me/inbody-ocr` (Tiếp nhận ảnh, gọi OCR service)<br>• `/chat/complete` (BFF endpoint nhận chat từ UI) | • `/v1/agent/chat` (Hội thoại đa tác tử chính)<br>• `/v1/agent/fast-path` (Đánh giá triage an toàn)<br>• `/v1/tools/*` (Tính BMI, PBF, BMR độc lập)<br>• `/v1/rag/search` (Tra cứu hybrid search)<br>• `/v1/rag/index` (Quản trị ingestion corpus) |
| **Quyền truy cập DB** | **Độc quyền** đọc/ghi PostgreSQL & Valkey Session | **Tuyệt đối không kết nối PostgreSQL** |
| **Kết nối AI / RAG** | Không kết nối Qdrant, không kết nối LLM | Kết nối Qdrant, BGE-M3 serving, Ollama/OpenAI |

### 4.2. Kế hoạch di dời chi tiết từng file trong `backend/src/`

```text
THƯ MỤC NGUỒN (backend/src/)             DỊCH VỤ ĐÍCH (core-api HOẶC agent-service)
───────────────────────────────────────────────────────────────────────────────────────────
src/auth/                      ───────>  core-api/src/auth/ (Xác thực JWT, CurrentUser)
src/persistence/               ───────>  core-api/src/persistence/ (Database, Models, Service)
src/api/personalization.py     ───────>  core-api/src/api/routes/personalization.py
src/api/inbody_ocr.py          ───────>  core-api/src/api/routes/ocr_proxy.py
src/api/memory.py              ───────>  core-api/src/api/routes/memory.py
src/jobs/                      ───────>  core-api/src/jobs/ (Celery Tasks điều phối lịch sử)

src/agents/                    ───────>  agent-service/src/agents/ (LangGraph, nodes, composer)
src/rag/                       ───────>  agent-service/src/rag/ (Qdrant client, BM25, rerank)
src/llm/                       ───────>  agent-service/src/llm/ (Ollama, OpenAI, Circuit Breaker)
src/health/                    ───────>  agent-service/src/health/ (Công cụ tính BMI, TDEE, Safety)
src/memory/                    ───────>  agent-service/src/memory/ (Zep/Working context adapter)
src/integrations/              ───────>  agent-service/src/integrations/ (Tavily search)
```

---

## 5. HỢP ĐỒNG GIAO TIẾP LIÊN DỊCH VỤ (INTER-SERVICE CONTRACT)

Khi `core-api` nhận yêu cầu chat từ người dùng tại endpoint `/chat/complete`, nó sẽ chuẩn bị dữ liệu xác thực và gọi sang `agent-service` qua giao thức HTTP REST/SSE.

### 5.1. Request Contract: `core-api` $\to$ `agent-service`
**Endpoint:** `POST http://agent-service:8001/v1/agent/chat`

```json
{
  "request_id": "req-98f7a2c1-20261026-0012",
  "principal": {
    "user_id": "usr-88231",
    "role": "authenticated_user",
    "tenant_id": "default"
  },
  "question": "Tôi nặng 72kg, cao 1m70, mỡ nội tạng mức 11 thì có nguy cơ gì không?",
  "history": [
    {"role": "user", "content": "Xin chào bác sĩ"},
    {"role": "assistant", "content": "Chào bạn, tôi là trợ lý sức khỏe InBody..."}
  ],
  "personalization_context": {
    "available": true,
    "gender": "male",
    "birth_year": 1998,
    "medical_conditions": ["none"],
    "latest_measurement": {
      "measurement_date": "2026-10-20",
      "weight_kg": 72.0,
      "height_cm": 170.0,
      "bmi": 24.91,
      "pbf_percent": 23.5,
      "visceral_fat_level": 11.0,
      "smm_kg": 31.2
    }
  },
  "client_options": {
    "stream": false,
    "temperature": 0.0,
    "timeout_seconds": 30
  }
}
```

### 5.2. Response Contract: `agent-service` $\to$ `core-api`
**Chuẩn phong bì đồng nhất (Uniform API Envelope):**

```json
{
  "success": true,
  "data": {
    "answer": "Với chỉ số BMI 24.91 kg/m² (tiệm cận tiền béo phì theo chuẩn WPRO) và mỡ nội tạng mức 11 (ngưỡng cảnh báo cao > 10)...",
    "status": "ok",
    "fast_path": null,
    "selected_agents": ["InBodyAgent", "NutritionAgent", "ResponseComposer"],
    "agent_trace": [
      {"agent": "SupervisorAgent", "action": "route_to_specialists", "status": "success"},
      {"agent": "InBodyAgent", "action": "evaluate_visceral_fat", "status": "success"}
    ],
    "tool_results": [
      {"tool": "calculate_bmi", "result": {"bmi": 24.91, "category": "Thừa cân/Tiền béo phì"}},
      {"tool": "evaluate_visceral_fat", "result": {"level": 11, "risk": "High"}}
    ],
    "evidence": [
      {
        "source": "inbody_clinical_guidelines_2026.md",
        "snippet": "Mức mỡ nội tạng từ 10 trở lên làm tăng nguy cơ mắc hội chứng chuyển hóa...",
        "confidence": 0.92
      }
    ],
    "safety_result": {
      "is_safe": true,
      "risk_level": "low",
      "flags": []
    }
  },
  "error": null,
  "meta": {
    "request_id": "req-98f7a2c1-20261026-0012",
    "latency_ms": 1420.5,
    "tokens_used": 680,
    "model_name": "qwen2.5:7b-instruct"
  }
}
```

---

## 6. THAY ĐỔI HẠ TẦNG & CẤU HÌNH DOCKER COMPOSE

Trong file [docker-compose.yml](file:///c:/Users/Admin/Desktop/KLTN/LLL%20RAG/backend/docker-compose.yml), container `chatbot-api` được phân tách thành 2 container:

```yaml
version: '3.8'

networks:
  internal-network:
    name: internal-network
    external: true

services:
  # ==========================================
  # SERVICE 1: CORE BUSINESS API (PORT 8000)
  # ==========================================
  core-api:
    build:
      context: ./core-api
      dockerfile: Dockerfile
    container_name: health-core-api
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    restart: always
    environment:
      - PORT=8000
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-db:5432/health_db
      - REDIS_HOST=valkey-db
      - AGENT_SERVICE_URL=http://agent-service:8001
      - OCR_SERVICE_URL=http://ocr-api:18100
      - AUTH_MODE=production
    ports:
      - "8000:8000"
    depends_on:
      - agent-service
    networks:
      - internal-network

  # ==========================================
  # SERVICE 2: AGENTIC AI PLATFORM (PORT 8001)
  # ==========================================
  agent-service:
    build:
      context: ./agent-service
      dockerfile: Dockerfile
    container_name: health-agent-service
    command: uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1
    restart: always
    environment:
      - PORT=8001
      - QDRANT_URL=http://qdrant-db:6333
      - CUSTOM_EMBEDDING_API_URL=http://embedding-api:5000
      - LLM_PROVIDER=ollama
      - OLLAMA_HOST=http://host.docker.internal:11434
      - OLLAMA_MODEL=qwen2.5:7b-instruct
      - BM25_SNAPSHOT_PATH=/app/data/bm25_snapshot.json.gz
    ports:
      - "8001:8001"
    networks:
      - internal-network

  # ==========================================
  # ASYNC WORKER: CELERY WORKER
  # ==========================================
  core-worker:
    build:
      context: ./core-api
      dockerfile: Dockerfile
    container_name: health-core-worker
    command: celery -A app.jobs.tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-db:5432/health_db
      - REDIS_HOST=valkey-db
      - AGENT_SERVICE_URL=http://agent-service:8001
    networks:
      - internal-network
```

---

## 7. ĐÁNH GIÁ RỦI RO & BIỆN PHÁP BẢO VỆ (RISK & MITIGATION)

| Rủi ro kỹ thuật | Mức độ | Hậu quả | Giải pháp xử lý triệt để |
| :--- | :---: | :--- | :--- |
| **Độ trễ gọi liên dịch vụ (Inter-service Latency)** | Trung bình | Tăng 5–15ms cho mỗi request HTTP giữa `core-api` và `agent-service`. | Sử dụng `httpx.AsyncClient` tái sử dụng HTTP Connection Pool (Keep-Alive); đối với chat dài thì dùng luồng **Server-Sent Events (SSE)** truyền token trực tiếp từ Agent qua Core về Frontend. |
| **Tràn VRAM GPU 4GB** | Cao | Crash cả LLM và BGE-M3 nếu cả 2 dịch vụ cùng tranh chấp GPU. | `core-api` hoàn toàn không chạm vào GPU. Chỉ duy nhất `agent-service` tương tác với GPU. Áp dụng quy tắc: Fast-path và BMI tool chạy thuần CPU trên Agent; LLM inference cấu hình ngữ cảnh ngắn (< 4096 tokens). |
| **Vỡ bộ test cũ (Regression)** | Cao | Toàn bộ 40+ unit test trong `backend/tests/` đang import in-process sẽ báo lỗi module. | Giữ nguyên mock contract: Viết một `MockAgentServiceClient` trong `core-api/tests` và test contract schema bằng `pytest`. Các test graph chuyển nguyên vẹn sang `agent-service/tests`. |
| **Bảo mật rò rỉ dữ liệu giữa 2 User** | Nghiêm trọng | Nếu `agent-service` lưu cache bộ nhớ nhầm session của user khác. | `agent-service` thiết kế theo chuẩn **Stateless Reasoning**: Mỗi request gửi sang bắt buộc phải chứa `thread_id` hoặc ngữ cảnh độc lập. Agent không lưu trạng thái phiên vào RAM toàn cục (No Global State). |

---

## 8. LỘ TRÌNH THỰC THI 5 BƯỚC (STEP-BY-STEP ROADMAP)

Để đảm bảo an toàn tuyệt đối theo đúng điều lệ trong [AGENTS.md](file:///c:/Users/Admin/Desktop/KLTN/LLL%20RAG/AGENTS.md) (*không làm hỏng test cũ, không triển khai nóng vội*), việc phân tách sẽ thực hiện theo 5 bước:

```mermaid
graph LR
    P1["Bước 1: Chuẩn bị\nTạo contracts/ & Dựng khung thư mục"] --> P2["Bước 2: Di dời Core\nAuth, Models, Postgres sang core-api"]
    P2 --> P3["Bước 3: Di dời Agent\nLangGraph, RAG, Health sang agent-service"]
    P3 --> P4["Bước 4: Nối mạch\nViết HTTP Client Core -> Agent"]
    P4 --> P5["Bước 5: Kiểm thử\nChạy E2E Smoke test & Cập nhật Compose"]
```

1. **Bước 1 (Foundation & Contracts):**
   * Tạo thư mục `contracts/` chứa Pydantic Schemas dùng chung giữa 2 bên (`AgentChatRequest`, `AgentChatResponse`, `UniformEnvelope`).
   * Tạo cấu trúc thư mục rỗng cho `core-api/` và `agent-service/`.
2. **Bước 2 (Migrate Core Business API):**
   * Chuyển mã nguồn `auth/`, `persistence/`, các route `/me/*`, `/inbody-ocr` sang `core-api`.
   * Kiểm tra để `core-api` khởi động độc lập và pass toàn bộ test database/auth.
3. **Bước 3 (Migrate Agentic AI Platform):**
   * Chuyển `agents/`, `rag/`, `llm/`, `health/` sang `agent-service`.
   * Dựng FastAPI app cho `agent-service` với các route `/v1/agent/chat` và `/v1/tools/*`.
   * Chạy unit test của Agent trên `agent-service` độc lập.
4. **Bước 4 (Wire Communication & BFF):**
   * Viết `AgentPlatformClient` trong `core-api` sử dụng `httpx` async để gọi sang `agent-service`.
   * Endpoint `/chat/complete` của `core-api` nhận request -> lấy profile InBody từ Postgres -> gọi `agent-service` -> nhận kết quả -> lưu lịch sử chat vào Postgres -> trả về Frontend.
5. **Bước 5 (Compose Integration & HTTP Smoke Test):**
   * Cập nhật `docker-compose.yml`.
   * Chạy 9 bài kiểm thử bắt buộc theo `AGENTS.md`: Health check, Lời chào, BMI 72kg/170cm, Đau ngực khó thở (Fast-path), InBody, Nutrition, Training, Safety Retrieval, Input âm trả 422.

---
*Báo cáo được lưu trữ chính thức làm căn cứ triển khai hệ thống.*

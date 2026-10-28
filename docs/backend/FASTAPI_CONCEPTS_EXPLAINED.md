# FastAPI Backend Concepts & API Contracts

File `backend/src/api/app.py` là entrypoint ứng dụng FastAPI của dự án **Health/InBody Multi-Agent RAG**. Ứng dụng cung cấp các endpoint cho hỏi đáp AI, tính toán chỉ số, tìm kiếm kết hợp (hybrid search) và nhóm API cá nhân hóa theo dõi tiến độ sức khỏe.

---

## 1. App Metadata & Startup Lifecycle

```python
app = FastAPI(
    title="Health/InBody Agent RAG Backend",
    version="1.0.0-beta",
)
```

Khi khởi động (`@app.on_event("startup")`):
- Hệ thống tự động nạp snapshot BM25 dạng JSON-Gzip (`backend/data/generated/bm25_snapshot.json.gz`) vào bộ nhớ nếu biến môi trường `BM25_AUTOLOAD=true`.
- Nếu file snapshot chưa có, hệ thống cảnh báo và chạy ở chế độ fallback sang Dense Vector Retrieval thuần túy trên Qdrant.

---

## 2. API Hỏi Đáp Chính (`/agent/answer`)

Đây là endpoint chuẩn được frontend Streamlit và bộ kiểm thử golden suite sử dụng:

### Request Schema (`AgentRequest`)
```json
{
  "question": "Tôi nam, 72kg, cao 170cm, tính BMI và cho lời khuyên ăn uống giảm mỡ",
  "history": [],
  "user_id": "demo-user"
}
```

### Response Schema (`AgentResponse Contract`)
```json
{
  "answer": "Chỉ số BMI của bạn là 24.91 (thể trạng bình thường)...",
  "status": "ok",
  "fast_path": null,
  "latency_ms": 1420.5,
  "agent_trace": [
    {"agent": "SupervisorAgent", "action": "select_agents", "status": "success"},
    {"agent": "InBodyAgent", "action": "evaluate_inbody_metrics", "status": "success"},
    {"agent": "NutritionAgent", "action": "suggest_nutrition", "status": "success"}
  ],
  "selected_agents": ["InBodyAgent", "NutritionAgent", "SafetyAgent"],
  "tool_results": [...],
  "retrieved_docs": [...],
  "citations": [
    {"id": "doc-001", "source": "inbody_guideline.pdf", "snippet": "..."}
  ],
  "evidence_status": "supported",
  "limitations": [],
  "safety_result": {"risk_level": "low", "warnings": []},
  "personalization_used": {},
  "errors": []
}
```

*Lưu ý:* Đối với ca khẩn cấp y tế hoặc tính BMI thuần túy, trường `"fast_path"` sẽ mang giá trị tương ứng (`"urgent_safety"` hoặc `"bmi_calculation"`), phản hồi trả về trong vòng 10–40ms.

---

## 3. Endpoint Chat Tương Thích Ngược (`/chat/complete`)

Dành cho các ứng dụng client yêu cầu cấu trúc tin nhắn OpenAI hoặc hỗ trợ xử lý nền bất đồng bộ (Celery):
- `POST /chat/complete`: Hỗ trợ `sync_request=true` (đồng bộ trực tiếp) hoặc `sync_request=false` (giao việc cho Celery task và nhận lại `task_id`).
- `GET /chat/complete/{task_id}`: Lấy kết quả chat từ task Celery.

---

## 4. Nhóm API Cá Nhân Hóa & Theo Dõi Tiến Độ (`/me/*`)

Được triển khai trong pha P1 ([api/personalization.py](file:///c:/Users/Admin/Desktop/KLTN/LLL RAG/backend/src/api/personalization.py)) với nguyên tắc bảo mật: danh tính người dùng được trích xuất từ Auth context (`request.state.current_user`), ngăn chặn tuyệt đối truy cập chéo dữ liệu giữa các user.

### 4.1 Hồ Sơ & Mục Tiêu (`/me/profile`, `/me/goals`)
- `GET /me/profile`: Lấy thông tin thể trạng cơ bản (tuổi, giới tính, chiều cao, hạn chế vận động).
- `PUT /me/profile`: Cập nhật toàn bộ hồ sơ.
- `PATCH /me/profile`: Cập nhật từng trường có kiểm soát.
- `GET /me/goals/current`: Lấy mục tiêu luyện tập hiện tại (ví dụ: giảm mỡ, tăng cơ).
- `PUT /me/goals/current`: Tạo phiên bản mục tiêu mới (mục tiêu cũ tự động chuyển trạng thái `superseded`).

### 4.2 Lịch Sử Đo InBody & Tiến Độ (`/me/measurements`, `/me/progress`)
- `GET /me/measurements`: Phân trang theo con trỏ (`cursor-based`) danh sách các lần đo InBody.
- `POST /me/measurements`: Thêm bản ghi đo mới (chiều cao, cân nặng, SMM, BFM, PBF, mỡ nội tạng). Server tự tính lại BMI để kiểm tra tính nhất quán.
- `PATCH /me/measurements/{id}`: Chỉnh sửa bản ghi do chính mình tạo hoặc đánh dấu xác nhận (`confirmed_by_user=true`).
- `DELETE /me/measurements/{id}`: Xóa mềm (`soft delete`).
- `GET /me/progress/summary`: Tóm tắt tiến độ, tính độ chênh lệch (`delta`) giữa lần đo đầu và lần đo gần nhất đã xác nhận.

### 4.3 Kế Hoạch & Check-in (`/me/plans`, `/me/checkins`)
- `POST /me/plans`: Tạo kế hoạch tập luyện/dinh dưỡng cá nhân hóa có liên kết snapshot mục tiêu và bằng chứng tài liệu.
- `POST /me/checkins`: Ghi nhận nhật ký triệu chứng hoặc tiến độ hàng ngày (tự động kích hoạt kiểm tra an toàn y tế nếu người dùng báo cáo triệu chứng bất thường).

---

## 5. Endpoints Kiểm Tra & Vận Hành

- `GET /health`: Kiểm tra sức khỏe toàn diện của API, cache, embedding connection, vector collection status, model runtime và trạng thái nạp BM25 snapshot.
- `POST /search`: Endpoint cho lập trình viên thử nghiệm Hybrid Retrieval trực tiếp trên corpus.

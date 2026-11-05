# Danh mục Hợp đồng API & Service (Contract Inventory)

> **Bằng chứng lịch sử:** Bảng Core → Agent dưới đây mô tả Profile B đã rút ngày 2026-11-05. Không dùng làm contract hiện hành của backend gộp.

**Phiên bản:** WP-00 Baseline, đối chiếu lại DTO khi rà soát WP-01.

**Ngày đối chiếu:** 2026-11-05.

---

## 1. Endpoints công khai & BFF Mapping

| Endpoint | Method | Trách nhiệm | Schema Request | Schema Response / Envelope | Consumer |
|---|---|---|---|---|---|
| `/health` | GET | Liveness/Readiness | None | Flat JSON (Backend A) hoặc UniformEnvelope (Core-API B) | Frontend, Load Balancer |
| `/chat/complete` | POST | Trò chuyện tổng quát & InBody | `CompleteRequest` (`user_message`, `bot_id`, `conversation_id`, `user_id`, `history`) | `{ "response": { "content", "status", "selected_agents", "evidence", ... } }` ở Core B; profile A có thêm trường riêng | Frontend (`api.ts:sendChatMessageApi`) |
| `/agent/answer` | POST | Trực tiếp Agent RAG (Profile A) | `AgentRequest` (`question`, `conversation_id`, `history`) | Full Agent Answer + Citations + Trace | Evals, Direct Integrations |
| `/me/profile` | GET / PUT | Quản lý thông tin & Consent | `ProfileUpdate` khi PUT | JSON theo persistence service | Frontend Dashboard & Settings |
| `/me/measurements` | GET / POST | Chỉ số InBody của người dùng | `MeasurementCreate` khi POST | Measurement JSON / danh sách | Frontend History & Charts |
| `/me/inbody-ocr` | POST | Trích xuất OCR phiếu InBody | Multipart Form `file` | `OcrResult` (`extracted_fields`, `unresolved_fields`, `warnings`) | Frontend OcrScanner component |

---

## 2. Inter-Service Contract (Core-API -> Agent-Service)

Được định nghĩa tại `contracts/agent.py` và `contracts/envelope.py`:

- **Path:** `POST /v1/agent/chat` trên `agent-service:8001`
- **Request DTO:** `AgentChatRequest` (không có lớp envelope cho request)
  - `request_id`: `str` (mặc định `req-` + 12 ký tự hex, không phải UUID nguyên vẹn)
  - `principal`: `Principal` (`user_id`, `role`, `tenant_id`)
  - `question`: `str`
  - `history`: `List[HistoryTurn]`
  - `personalization_context`: `Optional[PersonalizationContext]`
  - `conversation_id`: `Optional[str]`
  - `timeout_seconds`: `int` (mặc định 30 trong DTO; Core client timeout riêng lấy từ cấu hình, hiện mặc định 45)
- **Response Envelope:** `UniformEnvelope[AgentChatResponse]`
  - `success`: `bool`
  - `data`: `AgentChatResponse`
    - `answer`: `str`
    - `status`: `"ok" | "degraded" | "error"`
    - `fast_path`: `Optional[str]`
    - `selected_agents`: `List[str]`
    - `agent_trace`: `List[AgentTraceItem]`
    - `evidence`: `List[Dict[str, Any]]` (Core B trả `evidence` trong `/chat/complete` và đổi sang `citations` trong `/agent/answer`)
    - `claim_evidence_links`: `List[Dict[str, Any]]`
    - `retrieved_docs`: `List[Dict[str, Any]]`
    - `evidence_status`: `str`
    - `limitations`: chưa có trong `AgentChatResponse` DTO; phải kiểm kê/đưa vào contract ở WP-02 nếu cần giữ parity với Profile A
    - `tool_results`, `safety_result`, `errors`: các trường có trong DTO
    - `latency_ms`: `float`
  - `error`: `Optional[APIError]`
  - `meta`: `Dict[str, Any]`

**Giới hạn:** bảng này phản ánh source hiện tại, chưa xác minh image sạch hoặc HTTP runtime. `Principal` trong body hiện chưa được Agent xác thực như service identity; đây là gate của WP-03.

**Quyết định phạm vi 2026-11-05:** người dùng không cần Zep. External-memory consent, đồng bộ và thu hồi qua Zep không thuộc gate WP-01/Profile B. Agent không được gọi Zep từ `principal` hoặc context do request mang đến; Core giữ PostgreSQL memory/context cần cho nghiệp vụ. Các endpoint external-memory cũ phải báo rõ không hỗ trợ và không ghi consent hay gọi provider.

---

## 3. Tool Direct Endpoints (`agent-service:8001`)

- `POST /v1/tools/bmi`: Tính BMI từ `weight_kg` và `height_cm`.
- `POST /v1/tools/pbf`: Đánh giá phần trăm mỡ cơ thể.
- `POST /v1/tools/visceral-fat`: Đánh giá mỡ nội tạng.
- `POST /v1/tools/safety`: Kiểm tra khẩn cấp y tế.
- `POST /v1/tools/nutrition`: Gợi ý dinh dưỡng.
- `POST /v1/tools/training`: Gợi ý kế hoạch tập luyện.


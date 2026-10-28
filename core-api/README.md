# Core Business API Service (`core-api`)

Dịch vụ Cổng Nghiệp vụ & Xác thực (BFF & Business Core) cho nền tảng Health/InBody Agent RAG.

## Trách nhiệm chính:
1. **Xác thực & Danh tính (Auth & Principal):** Xử lý JWT, API Key và bóc tách `Principal` định danh người dùng.
2. **Cơ sở dữ liệu Nguồn (SSOT):** Độc quyền đọc/ghi cơ sở dữ liệu PostgreSQL (`user_profiles`, `inbody_measurements`, `health_goals`, `daily_check_ins`).
3. **Cổng giao tiếp Frontend (BFF):** Cung cấp các REST endpoint `/me/*` cho giao diện người dùng (Streamlit / React).
4. **Điều phối Tác tử:** Tiếp nhận yêu cầu chat tại `/chat/complete`, tải ngữ cảnh InBody từ PostgreSQL, che giấu PII và gọi sang `agent-service:8001`.
5. **Điều phối OCR:** Tiếp nhận ảnh phiếu InBody tại `/me/inbody-ocr` và chuyển tiếp đến `ocr-service:18100`.

## Cổng dịch vụ (Port):
* **HTTP Port:** 8000

# Tóm Tắt Đề Tài Tốt Nghiệp

## Tên đề tài: Xây dựng hệ thống AI phân tích kết quả InBody và tư vấn cải thiện sức khỏe người dùng (Health/InBody Multi-Agent RAG)

### 1. Đặt vấn đề
Kết quả đo InBody hiện nay thường được cung cấp dưới dạng ảnh hoặc bản in với nhiều mẫu trình bày khác nhau tùy theo thiết bị và cơ sở đo. Các chỉ số sức khỏe quan trọng như BMI, khối lượng cơ xương (SMM), khối lượng mỡ (BFM), tỷ lệ phần trăm mỡ cơ thể (PBF) và phân bố cơ thể thường được thể hiện dưới dạng văn bản, bảng số hoặc biểu đồ, gây khó khăn cho người dùng phổ thông trong việc tự đọc hiểu và xây dựng lộ trình cải thiện thể trạng an toàn.

Do đó, đề tài xây dựng một hệ thống trợ lý thông minh đa tác nhân (Multi-Agent RAG) có khả năng đọc hiểu chỉ số InBody, đối soát kiến thức sức khỏe có bằng chứng (evidence-backed retrieval), cảnh báo an toàn y tế và đưa ra tư vấn cá nhân hóa về dinh dưỡng, tập luyện.

### 2. Mục tiêu đề tài
- **Hiểu và chuẩn hóa chỉ số:** Xử lý các chỉ số InBody (chiều cao, cân nặng, BMI, PBF, SMM, mỡ nội tạng) thành hồ sơ có cấu trúc, đánh giá phân loại thể trạng khoa học.
- **Hệ thống Multi-Agent RAG:** Ứng dụng LangGraph để phối hợp các tác tử chuyên biệt:
  - `InBodyAgent`: Đánh giá các chỉ số cơ thể.
  - `NutritionAgent`: Tính toán chiến lược calo và nhu cầu protein/macro.
  - `TrainingAgent`: Đề xuất lịch tập luyện kháng lực/cardio theo tuần.
  - `RAGAgent`: Truy xuất kiến thức chuyên sâu từ kho tài liệu sức khỏe đã kiểm chứng.
  - `SafetyAgent`: Kiểm soát rủi ro y tế, ngăn chặn chẩn đoán hoặc kê đơn sai quy định.
- **Fast-path bảo vệ an toàn y tế:** Phản hồi tức thì (< 50ms) đối với các triệu chứng nguy hiểm (đau ngực, khó thở, ngất xỉu) mà không thông qua LLM để loại trừ hoàn toàn nguy cơ ảo giác.
- **Theo dõi tiến bộ (Progress Tracking):** Lưu trữ lịch sử đo theo thời gian của từng người dùng, tính toán chênh lệch (`delta`) giữa các lần đo và chỉ dùng dữ liệu đã được người dùng xác nhận để cá nhân hóa lời khuyên.
- **Hỗ trợ tiếng Việt:** Giao diện trực quan qua Streamlit Web UI, giải thích rõ ràng và có trích dẫn nguồn tài liệu tham khảo.

### 3. Phạm vi hệ thống
- **Đầu vào (Input):**
  - Câu hỏi tự nhiên bằng tiếng Việt.
  - Chỉ số InBody nhập dạng văn bản trong khung chat.
  - Thông tin bổ sung: tuổi, giới tính, mức độ vận động, mục tiêu (giảm mỡ, tăng cơ, duy trì), hạn chế thể lực hoặc bệnh lý nền.
  - Lịch sử đo InBody qua API `/me/measurements`.
- **Đầu ra (Output):**
  - Đánh giá phân loại chỉ số thể trạng.
  - Kế hoạch dinh dưỡng và tập luyện tham khảo 3–6 tháng.
  - Trích dẫn nguồn tham khảo thực tế (`citations`, `evidence`).
  - Cảnh báo an toàn y tế bắt buộc khi có dấu hiệu bất thường.

### 4. Công nghệ sử dụng
- **Backend:** Python 3.10+, FastAPI, LangGraph, Pydantic v2.
- **LLM & Inference:** Hỗ trợ linh hoạt Ollama (Qwen 8B, v.v.) và OpenAI API.
- **Retrieval & Vector DB:** Qdrant Vector Database, mô hình embedding BAAI/BGE-M3 (1024-dim), kết hợp BM25 sparse snapshot (Hybrid Search).
- **Database & Cache:** PostgreSQL (lưu profile, goal, measurement, plan), Valkey/Redis (cache & Celery broker).
- **Frontend:** Streamlit.
- **Containerization:** Docker & Docker Compose.

### 5. Lộ trình phát triển tiếp theo (Roadmap)
- **P2:** Tích hợp bộ quét OCR trích xuất chỉ số tự động từ ảnh chụp/PDF phiếu InBody.
- **Mở rộng Corpus:** Bổ sung metadata nguồn và kiểm duyệt lâm sàng từ chuyên gia y tế.

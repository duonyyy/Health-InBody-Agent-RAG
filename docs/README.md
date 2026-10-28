# Thư Mục Tài Liệu Hệ Thống (Documentation Index)

Chào mừng bạn đến với kho tài liệu của dự án **Health/InBody Multi-Agent RAG** (Hệ thống AI phân tích chỉ số InBody và tư vấn cải thiện sức khỏe người dùng).

Tài liệu được phân loại theo từng nhóm chuyên môn dưới đây:

---

## 📌 1. Đề Tài & Tổng Quan Dự Án

*   [TOM_TAT_DE_TAI.md](TOM_TAT_DE_TAI.md): Tóm tắt đề tài Khóa luận Tốt nghiệp (bài toán, mục tiêu, kiến trúc, phạm vi).
*   [../README.md](../README.md): Tổng quan toàn diện về hệ thống, sơ đồ kiến trúc Multi-Agent RAG, thiết kế API và lộ trình chung.
*   [../ARCH.MD](../ARCH.MD): Chi tiết kiến trúc hệ thống, sơ đồ tương tác giữa các services và database schema.
*   [../SETUP.md](../SETUP.md): Hướng dẫn thiết lập môi trường và khởi chạy hệ thống (Docker Compose, cấu hình phần cứng).

---

## 🎯 2. Lộ Trình Triển Khai & Tiêu Chí Nghiệm Thu (Roadmap)

Kế hoạch nâng cấp hệ thống từ MVP lên Agent RAG Beta với các Quality Gates nghiêm ngặt:

*   [implementation-roadmap/README.md](implementation-roadmap/README.md): Tổng quan lộ trình triển khai theo các pha P0, P1, P2.
*   [implementation-roadmap/00-p0-trust-rag-safety.md](implementation-roadmap/00-p0-trust-rag-safety.md): **P0** — Cơ chế Trust RAG, an toàn y tế và độ tin cậy runtime (Fast-path, citation contract, BM25 snapshot).
*   [implementation-roadmap/01-p1-progress-and-personalization.md](implementation-roadmap/01-p1-progress-and-personalization.md): **P1** — Cá nhân hóa, theo dõi tiến độ đo InBody và bảo mật dữ liệu người dùng (`/me` API).
*   [implementation-roadmap/02-p2-ocr-privacy-and-live-web.md](implementation-roadmap/02-p2-ocr-privacy-and-live-web.md): **P2** — Kế hoạch tích hợp OCR trích xuất ảnh/PDF InBody và tìm kiếm web thời gian thực.
*   [implementation-roadmap/03-evaluation-and-acceptance.md](implementation-roadmap/03-evaluation-and-acceptance.md): Bộ tiêu chí đánh giá, benchmark và quyết định Go/No-go cho từng release.

---

## 📊 3. Báo Cáo Nghiệm Thu & Kiểm Thử (Reports & Testing)

*   [P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md](P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md): Báo cáo nghiệm thu P0 — Kiểm chứng 6/6 golden test ca an toàn y tế, BMI fast-path, nạp 23.608 tài liệu BM25 và hợp đồng trích dẫn.
*   [P1_PERSONALIZATION_REPORT.md](P1_PERSONALIZATION_REPORT.md): Báo cáo nghiệm thu P1 — Kiểm chứng 59 unit/integration tests và 39/39 HTTP checks thực tế (bảo vệ quyền riêng tư, cách ly dữ liệu user, tính toán delta tiến độ).
*   [test.md](test.md): Bộ câu hỏi mẫu (Golden test queries) dùng để kiểm thử và demo Multi-Agent RAG.

---

## ⚙️ 4. Kiến Trúc Backend & Multi-Agent RAG

Tài liệu giải thích chi tiết các module trong `backend/src/`:

*   [backend/AI_AGENT_REACT_EXPLAINED.md](backend/AI_AGENT_REACT_EXPLAINED.md): Chi tiết luồng điều phối LangGraph Multi-Agent, danh sách tác tử, Agent State và các cơ chế Fast-path.
*   [backend/FASTAPI_CONCEPTS_EXPLAINED.md](backend/FASTAPI_CONCEPTS_EXPLAINED.md): Thiết kế FastAPI backend, hợp đồng endpoint `/agent/answer`, `/chat/complete` và nhóm API cá nhân hóa `/me`.
*   [backend/HYBRID_SEARCH_EXPLAINED.md](backend/HYBRID_SEARCH_EXPLAINED.md): Cơ chế tìm kiếm kết hợp Hybrid Search (Dense vector trên Qdrant + Versioned BM25 JSON-Gzip Snapshot).
*   [backend/CELERY_TASKS_EXPLAINED.md](backend/CELERY_TASKS_EXPLAINED.md): Cơ chế xử lý tác vụ nền bất đồng bộ qua Celery và Valkey.
*   [backend/TAVILY_SEARCH_EXPLAINED.md](backend/TAVILY_SEARCH_EXPLAINED.md): Tích hợp tìm kiếm thông tin web mở rộng thông qua Tavily API.
*   [backend/SIMPLE_CI_CD_GUIDE.md](backend/SIMPLE_CI_CD_GUIDE.md): Hướng dẫn thiết lập quy trình kiểm thử tự động CI/CD cho backend.
*   [backend/KE_HOACH_TAI_CAU_TRUC_BACKEND.md](backend/KE_HOACH_TAI_CAU_TRUC_BACKEND.md): **Kế hoạch tái cấu trúc Backend** — Phân rã `agents/graph.py`, chuẩn hóa `api/app.py` và modular hóa APIRouter.

---

## 🗄️ 5. Quản Lý Dữ Liệu & Vector Database (Data Pipeline & Qdrant)

*   [DATA_IMPORT_FLOW_COMPLETE.md](DATA_IMPORT_FLOW_COMPLETE.md): Sơ đồ và quy trình chi tiết quá trình nạp tài liệu từ file JSONL vào Qdrant với embedding BGE-M3.
*   [QDRANT_BLUE_GREEN_IMPORT.md](QDRANT_BLUE_GREEN_IMPORT.md): Quy trình cập nhật và chuyển đổi collection trên Qdrant theo chiến lược Blue/Green không gián đoạn dịch vụ.
*   [datapipeline/DATA_PIPELINE_DOCUMENTATION.md](datapipeline/DATA_PIPELINE_DOCUMENTATION.md): Cấu trúc và tài liệu vận hành thư mục `data_pipeline/`.

---

## 🧠 6. Mô Hình Embedding (BGE-M3 Serving)

*   [embed/EMBEDDING_SERVING_DOCUMENTATION.md](embed/EMBEDDING_SERVING_DOCUMENTATION.md): Hướng dẫn triển khai service nhúng vector sử dụng mô hình BAAI/BGE-M3 (Port 5001).
*   [embed/BGE_M3_TECHNICAL_DEEP_DIVE.md](embed/BGE_M3_TECHNICAL_DEEP_DIVE.md): Phân tích kỹ thuật chuyên sâu về kiến trúc và đặc tính đa ngôn ngữ của BGE-M3.

---

## 📚 7. Tài Liệu Tham Khảo Kỹ Thuật (Reference)

*   [finetune/01_CODE_FINETUNE.md](finetune/01_CODE_FINETUNE.md): Khái niệm code Python nâng cao trong kịch bản train/fine-tune LLM.
*   [finetune/02_PARAMETER_FINETUNE.md](finetune/02_PARAMETER_FINETUNE.md): Giải thích chi tiết các siêu tham số huấn luyện (LoRA, learning rate, batch size).
*   [finetune/03_LLAMA_MODEL_TECHNICAL_DEEPDIVE.md](finetune/03_LLAMA_MODEL_TECHNICAL_DEEPDIVE.md): Phân tích kiến trúc kỹ thuật của dòng mô hình LLaMA.

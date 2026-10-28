# Tài Liệu Embedding Serving - Health/InBody Agent RAG System

## 📋 Tổng quan

Module Embedding Serving (`embed_serving/`) của hệ thống **Health/InBody Multi-Agent RAG** cung cấp **RESTful API** độc lập phục vụ mô hình embedding **BGE-M3** (BAAI/bge-m3), chuyển đổi văn bản y tế, dinh dưỡng, thể thao và chỉ số InBody thành các biểu diễn vector ngữ nghĩa 1024 chiều.

Hệ thống được thiết kế chạy container hóa qua Docker (`embed_serving/docker-compose.serving.yml`), cổng mặc định **5001**.

---

## 🎯 Vai Trò Trong Kiến Trúc RAG

Mô hình BGE-M3 phục vụ các tác vụ:
1. **🔍 Semantic Search:** Chuyển đổi câu hỏi của người dùng thành dense vector để tìm kiếm các tài liệu liên quan trong Qdrant.
2. **📚 Bulk Indexing:** Nhúng toàn bộ kho tài liệu sức khỏe, dinh dưỡng và bài tập trong giai đoạn data pipeline/indexing.
3. **⚡ CPU/GPU Inference Linh Hoạt:** Cho phép cấu hình chạy trên CPU (FP32) hoặc GPU (FP16 qua CUDA) tùy thuộc vào giới hạn VRAM (đặc biệt khi GPU 4GB dùng chung cho LLM).

---

## 🤖 Đặc Tính Kỹ Thuật Mô Hình BGE-M3

**BGE-M3** (BAAI General Embedding - Multilingual, Multi-Granularity, Multi-Functionality) là mô hình embedding đa ngôn ngữ tiên tiến:

*   **Paper:** [BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation](https://arxiv.org/abs/2402.03216)
*   **Kích thước vector (Embedding Dimension):** `1024`
*   **Chiều dài ngữ cảnh tối đa (Max Sequence Length):** `8192` tokens
*   **Đa ngôn ngữ (Multilingual):** Hỗ trợ xuất sắc tiếng Việt có dấu và không dấu, hiểu tốt thuật ngữ viết tắt y khoa và thể hình (`BMI`, `PBF`, `SMM`, `Visceral Fat`).

---

## 🏗️ Kiến Trúc Serving Module

### Công nghệ sử dụng
- **Framework:** Flask / Gunicorn (nhẹ, ít chiếm dụng RAM, phù hợp microservice nhúng độc lập).
- **Thư viện AI:** HuggingFace `sentence-transformers` / `FlagEmbedding`, `PyTorch`.

### Các Endpoints Cốt Lõi

1.  **Health Check Endpoint**
    *   `GET /health`: Kiểm tra trạng thái hoạt động của mô hình, thiết bị thực thi (CPU/CUDA) và cấu hình bộ nhớ.
2.  **Sinh Vector Nhúng (Embedding Generation)**
    *   `POST /embed`: Nhận danh sách các đoạn văn bản và trả về ma trận vector 1024 chiều.
    ```json
    // Request
    {
      "texts": ["Chỉ số PBF là tỷ lệ phần trăm mỡ cơ thể...", "Lịch tập cardio giảm mỡ"]
    }
    // Response
    {
      "embeddings": [[0.012, -0.045, ...], [0.089, 0.021, ...]],
      "model": "BAAI/bge-m3",
      "dim": 1024
    }
    ```
3.  **Tính Điểm Tương Đồng (Similarity)**
    *   `POST /similarity`: Tính độ tương tự Cosine giữa hai văn bản.

---

## ⚡ Cấu Hình & Tối Ưu Hiệu Năng

Trong môi trường GPU hạn chế (VRAM 4GB):
- Chạy online serving: Đề xuất chạy BGE-M3 trên CPU với batch size vừa phải (`batch_size = 8` hoặc `16`), dành toàn bộ VRAM GPU cho mô hình sinh (Ollama Qwen 8B).
- Chạy bulk import: Có thể tạm thời tắt LLM để dồn GPU chạy BGE-M3 FP16, tăng tốc độ nhúng hàng vạn tài liệu lên gấp 4–5 lần.
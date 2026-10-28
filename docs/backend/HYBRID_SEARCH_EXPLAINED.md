# Cơ Chế Tìm Kiếm Kết Hợp (Hybrid Search)

Module `backend/src/rag/search.py` triển khai giải pháp tìm kiếm kết hợp (Hybrid Search) cho hệ thống **Health/InBody Agent RAG**, kết hợp ưu điểm của tìm kiếm từ khóa chính xác (Sparse Retrieval - BM25) và tìm kiếm ngữ nghĩa theo vector (Dense Retrieval - BGE-M3 trên Qdrant).

---

## 1. Tại Sao Cần Hybrid Search?

Trong bài toán sức khỏe và chỉ số InBody:
1.  **Từ khóa cụ thể (Lexical):** Người dùng hỏi về các chỉ số hoặc thuật ngữ viết tắt như `BMI`, `PBF`, `SMM`, `Visceral Fat level 12`, `Whey Isolate`, hoặc tên các bệnh lý/thuốc. Vector embedding đôi khi có thể bị mờ nhạt hoặc nhầm lẫn giữa các thuật ngữ viết tắt có ngữ cảnh gần nhau.
2.  **Ngữ nghĩa tự nhiên (Semantic):** Người dùng đặt các câu hỏi tiếng Việt phong phú, đồng nghĩa hoặc gián tiếp: *"bụng to như bia thì nên giảm thế nào"*, *"người gầy nhưng bụng nhiều mỡ"*. BM25 đơn thuần sẽ không tìm được tài liệu nếu không trùng từ khóa chính xác.

Do đó, kết hợp cả hai phương pháp giúp cân bằng giữa độ chính xác từ khóa và khả năng bao quát ngữ nghĩa.

---

## 2. Các Thành Phần Chính

### 2.1 BM25 với Versioned Snapshot Cục Bộ
*   **Vị trí snapshot:** `backend/data/generated/bm25_snapshot.json.gz`.
*   **Quy mô:** Chứa 23.608 tài liệu đã phân đoạn từ corpus y tế/InBody (`corpus version: 2026-07-30-v2`).
*   **Cơ chế khởi động:** Khi backend khởi chạy, file nén gzip được giải nén và nạp trực tiếp vào RAM, đảm bảo chỉ số sẵn sàng ngay mà không cần đợi nạp lại từ Qdrant qua mạng.
*   **Tiền lọc (Pre-filtering theo `content_type`):**
    *   Trước khi chấm điểm BM25, hệ thống áp dụng bộ lọc theo loại nội dung (ví dụ: `medical_safety`, `inbody_metric`, `nutrition`).
    *   Ví dụ: Với truy vấn an toàn y tế (`medical_safety`), số lượng candidate giảm từ 23.608 xuống còn 4 tài liệu; thời gian lọc và chấm điểm chỉ mất **~0.23 ms**.
*   **Chuẩn hóa Tiếng Việt (Diacritics Normalization):**
    *   Tokenizer xử lý đồng thời văn bản tiếng Việt có dấu và không dấu, đảm bảo người dùng gõ không dấu (*"dang dung thuoc huyet ap"*) vẫn tìm thấy đúng 4/4 tài liệu an toàn y tế.

### 2.2 Dense Vector Search (Qdrant)
*   **Mô hình Embedding:** BAAI/BGE-M3 (1024 chiều) được phục vụ độc lập tại `embed_serving` (Port 5001).
*   **Cơ chế tìm kiếm:** Thực hiện Cosine Similarity Search trên collection active trong Qdrant (`nmk_chatbot_active`).
*   **Tối ưu hóa tài nguyên:** Nếu BM25 sau khi lọc `content_type` đã bao phủ toàn bộ một tập nhỏ tài liệu có độ liên quan tuyệt đối (ví dụ danh mục an toàn y tế), hệ thống sẽ chủ động bỏ qua bước gọi vector search để giảm tải VRAM/CPU và tiết kiệm thời gian phản hồi.

### 2.3 Cơ Chế Hòa Trộn Điểm Số (Score Fusion)
Điểm số cuối cùng của mỗi đoạn tài liệu được tính theo công thức trọng số kết hợp:

$$\text{Final Score} = \alpha \cdot \text{Dense Score} + (1 - \alpha) \cdot \text{Normalized BM25 Score}$$

Trong đó:
- $\alpha \approx 0.6$ (ưu tiên ngữ nghĩa nhưng vẫn đảm bảo trọng số từ khóa chính xác).
- Các tài liệu có điểm hòa trộn cao nhất được đưa vào danh sách ứng viên (top-k).

---

## 3. Quy Trình Truy Vấn Thực Tế

```text
[User Query]
     ↓
[Chuẩn hóa tiếng Việt & trích xuất intent]
     ↓
[Xác định content_type filter (nếu có)]
     ↓
┌───────────────────────────────────────┬───────────────────────────────────────┐
│              BM25 Search              │          Dense Vector Search          │
│   (Lọc candidate trước khi chấm điểm) │ (Gọi BGE-M3 embed -> Qdrant search)   │
└───────────────────────────────────────┴───────────────────────────────────────┘
     ↓                                       ↓
     └───────────────────┬───────────────────┘
                         ↓
               [Score Normalization]
                         ↓
            [Score Fusion / Re-ranking]
                         ↓
              [Top-K Retrieved Docs]
                         ↓
       [Đưa vào RAG Context kèm Citations ID]
```

---

## 4. Kiểm Thử & Hiệu Năng Đạt Được

Trong đợt nghiệm thu P0 ([P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md](../P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md)):
- **Tốc độ truy xuất BM25 lọc:** ~0.23 ms cho các danh mục nhỏ; ~200 ms cho truy vấn toàn văn 23.608 tài liệu.
- **Độ chính xác an toàn:** Đạt 100% trích xuất đúng tài liệu cảnh báo bệnh nền/thuốc mà không bị lẫn công thức dinh dưỡng hoặc bài tập thể hình.

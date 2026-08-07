# Giải Thích Hybrid Search

File `backend/src/search.py` triển khai hybrid search cho Health/InBody Agent RAG. Hybrid search kết hợp tìm kiếm keyword BM25 và tìm kiếm vector trong Qdrant để tăng khả năng truy xuất tài liệu liên quan.

## 1. Mục Tiêu

Người dùng có thể hỏi bằng ngôn ngữ tự nhiên:

```text
Mỡ nội tạng cao nên ăn uống và tập luyện thế nào?
```

Backend cần tìm các chunk liên quan về:

- InBody metrics: BMI, PBF, SMM, BFM, mỡ nội tạng.
- Dinh dưỡng: calo, protein, khẩu phần, giảm mỡ, tăng cơ.
- Tập luyện: cardio, kháng lực, lịch tập, phục hồi.
- An toàn y tế: triệu chứng nguy hiểm, bệnh nền, thuốc, gặp bác sĩ.

## 2. Thành Phần

### BM25 In-Memory

BM25 dùng keyword matching trên documents đã index vào bộ nhớ runtime:

```text
initialize_search_index(documents)
```

Ưu điểm:

- Tốt với từ khóa cụ thể như `BMI`, `PBF`, `protein`.
- Không cần embedding service khi chạy.

Hạn chế:

- Cần khởi tạo lại sau khi restart nếu chưa load từ Qdrant.
- Kém hơn vector search với câu hỏi diễn đạt khác từ.

### Vector Search Qdrant

Vector search dùng embedding từ `embed_serving`, sau đó search trong Qdrant:

```text
brain.get_embedding -> custom_embedding -> POST /embed
vectorize.search_vector -> Qdrant search
```

Ưu điểm:

- Tìm được tài liệu gần nghĩa.
- Phù hợp câu hỏi tiếng Việt diễn đạt tự nhiên.

Hạn chế:

- Phụ thuộc `embed_serving`.
- Collection Qdrant phải đúng vector size, mặc định `1024`.

### Rerank

Sau khi gộp kết quả, backend có thể gọi `rerank_documents` để xếp lại top documents theo query.

## 3. Luồng `hybrid_search`

```text
query
  -> expand_health_query
  -> bm25_search
  -> vector_search_fallback
  -> combine_search_results
  -> rerank_documents
  -> top results
```

### Bước 1: Expand Query

`expand_health_query()` bổ sung thuật ngữ liên quan. Ví dụ câu hỏi về PBF có thể được mở rộng thêm "phần trăm mỡ cơ thể".

### Bước 2: BM25 Search

`bm25_search()` tokenize query và documents, tính điểm BM25 rồi trả top candidates.

### Bước 3: Vector Search

`vector_search_fallback()`:

1. Gọi embedding service.
2. Search Qdrant collection `nmk_chatbot_collection`.
3. Gắn `vector_score`, `similarity_score`, `search_method`.

Nếu embedding service hoặc Qdrant lỗi, hàm trả danh sách rỗng để pipeline vẫn có thể dùng BM25.

### Bước 4: Gộp Điểm

`combine_search_results()` chuẩn hóa điểm BM25 và vector, sau đó tính:

```text
hybrid_score =
  dense_weight * vector_score
  + bm25_weight * bm25_score
  + hybrid_bonus
  + domain_bonus
```

Mặc định:

- `DENSE_WEIGHT=0.6`
- `BM25_WEIGHT=0.4`

### Bước 5: Rerank

Nếu `use_rerank=true`, kết quả cuối được rerank và cắt theo `limit`.

## 4. Metadata Quan Trọng

Mỗi payload trong Qdrant nên có:

| Field | Ý nghĩa |
| --- | --- |
| `doc_id` | ID tài liệu gốc |
| `chunk_id` | ID chunk |
| `question` hoặc `title` | Chủ đề/title |
| `content` | Nội dung chunk |
| `source` | Nguồn dữ liệu |
| `content_type` | `inbody_metric`, `nutrition`, `exercise`, `medical_safety`, `general_health` |
| `domain` | `health_inbody` |
| `language` | `vi` |

## 5. Dataset Đầu Vào

Data pipeline sinh corpus chính:

```text
data_pipeline/dataset/processed/embedding_documents.jsonl
```

Backend import file này bằng:

```bash
python backend/src/pipelines/import_data.py
```

Hoặc gửi qua API:

```bash
python data_pipeline/utils/index_mvp_dataset.py --batch-size 50
```

## 6. Khi Search Không Có Kết Quả

Kiểm tra theo thứ tự:

1. Qdrant container đã chạy chưa.
2. Collection `nmk_chatbot_collection` đã có points chưa.
3. `embed_serving` có trả `/health` healthy không.
4. `CUSTOM_EMBEDDING_API_URL` đúng chưa.
5. Collection vector size có khớp embedding dimension không.
6. BM25 index đã được khởi tạo chưa.

## 7. Ví Dụ API

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mỡ nội tạng cao nên làm gì",
    "limit": 5,
    "use_rerank": true
  }'
```

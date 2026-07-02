# Data Pipeline Documentation - Health/InBody Multi-Agent RAG MVP

## Tổng quan

`data_pipeline/` chuẩn bị corpus cho Health/InBody Multi-Agent RAG MVP. Pipeline hiện tại tập trung vào:

- Gom dữ liệu dinh dưỡng, thực phẩm, tài liệu fitness và các seed documents InBody.
- Extract text từ PDF khi có `pypdf`.
- Chuẩn hóa tài liệu RAG thành JSONL để backend index vào Qdrant/BM25.
- Tách riêng dữ liệu recommender (`foods_normalized.csv`, `ratings_normalized.csv`) khỏi corpus RAG.

Pipeline hiện tại thuộc phạm vi Health/InBody Multi-Agent RAG MVP.

## Cấu trúc chính

```text
data_pipeline/
├── configs/
├── dataset/
│   ├── raw/
│   │   ├── source_manifest.json
│   │   ├── foodrecordfinal/
│   │   ├── ratings/
│   │   ├── usda_fooddata/
│   │   ├── foodinfo/
│   │   └── fitness_documents/
│   ├── processed/
│   │   ├── all_raw_sources.jsonl
│   │   ├── embedding_documents.jsonl
│   │   ├── embedding_report.json
│   │   ├── embedding_build_report.json
│   │   ├── foods_normalized.csv
│   │   ├── ratings_normalized.csv
│   │   └── extracted_text/
│   └── rag_documents/
│       └── health_inbody_corpus.jsonl
└── utils/
    ├── merge_raw_sources.py
    ├── prepare_embedding_dataset.py
    ├── build_embedding_dataset.py
    └── index_mvp_dataset.py
```

## Nguồn dữ liệu

Nguồn được khai báo trong `data_pipeline/dataset/raw/source_manifest.json`:

| Source | Vai trò | Đưa vào RAG? |
| --- | --- | --- |
| `foodrecordfinal_foods` | Món ăn, dinh dưỡng, content-based recommendation | Có |
| `foodrecordfinal_ratings` | User-food ratings cho collaborative filtering | Không |
| `usda_fooddata_foundation` | Dữ liệu dinh dưỡng tham khảo | Có |
| `vietnam_food_composition_2007` | Bảng thành phần thực phẩm Việt Nam PDF | Có sau khi extract text |
| `fitness_training_document` | Tài liệu tập luyện fitness PDF | Có sau khi extract text |

## Luồng build corpus

```text
raw/source_manifest.json
  -> extract_pdf_sources
  -> merge_raw_sources.py
  -> processed/all_raw_sources.jsonl
  -> prepare_embedding_dataset.py
  -> processed/embedding_documents.jsonl
  -> rag_documents/health_inbody_corpus.jsonl
  -> index_mvp_dataset.py
  -> backend /documents/index
  -> Qdrant + BM25
```

## Script chính

### `merge_raw_sources.py`

Gom các nguồn raw thành `processed/all_raw_sources.jsonl`.

Đặc điểm:

- Không sửa dữ liệu trong `dataset/raw/`.
- Ghi `domain=health_inbody`.
- Tạo record cho foods, USDA, PDF extracted pages.
- Ratings được merge thành interaction records nhưng sẽ bị loại khỏi RAG corpus ở bước sau.

Chạy:

```bash
python data_pipeline/utils/merge_raw_sources.py
```

### `prepare_embedding_dataset.py`

Lọc và chuẩn hóa documents sẵn sàng embedding.

Chỉ giữ `content_type`:

- `nutrition`
- `exercise`
- `inbody_metric`
- `medical_safety`
- `general_health`

Bỏ qua:

- `recommender_interaction`
- PDF placeholder chưa extract text
- record có content quá ngắn

Script cũng thêm seed documents nội bộ về BMI, PBF, SMM, BFM, mỡ nội tạng, dinh dưỡng, tập luyện và safety.
Các seed documents này có metadata `source_name` và `source_url` để truy vết nguồn tham khảo trong demo RAG.

### `build_embedding_dataset.py`

Entry script nên dùng cho toàn pipeline.

Chạy:

```bash
python data_pipeline/utils/build_embedding_dataset.py
```

Output:

- `data_pipeline/dataset/processed/all_raw_sources.jsonl`
- `data_pipeline/dataset/processed/embedding_documents.jsonl`
- `data_pipeline/dataset/processed/embedding_report.json`
- `data_pipeline/dataset/processed/embedding_build_report.json`
- `data_pipeline/dataset/rag_documents/health_inbody_corpus.jsonl`
- `data_pipeline/dataset/processed/foods_normalized.csv`
- `data_pipeline/dataset/processed/ratings_normalized.csv`

### `index_mvp_dataset.py`

Gửi corpus sang backend để index vào Qdrant/BM25.

Backend cần chạy trước tại `http://localhost:8000`.

```bash
python data_pipeline/utils/index_mvp_dataset.py --batch-size 50
```

Test nhanh:

```bash
python data_pipeline/utils/index_mvp_dataset.py --limit 20 --batch-size 10
```

## Contract với backend

Mỗi dòng trong `embedding_documents.jsonl` cần có:

```json
{
  "doc_id": "string",
  "title": "string",
  "content": "string",
  "source": "string",
  "content_type": "nutrition | exercise | inbody_metric | medical_safety | general_health",
  "domain": "health_inbody",
  "language": "vi | en",
  "metadata": {}
}
```

Backend endpoint:

```http
POST /documents/index
Content-Type: application/json

{
  "collection_name": "nmk_chatbot_collection",
  "documents": [...]
}
```

## Trạng thái corpus hiện tại

Theo `embedding_build_report.json`:

- Tổng documents RAG: `5345`.
- `nutrition`: `4918`.
- `exercise`: `407`.
- `inbody_metric`: `15`.
- `medical_safety`: `4`.
- `general_health`: `1`.
- Domain: `health_inbody`.
- Validation: pass.
- Foods normalized: `4000` rows.
- Ratings normalized: `182631` rows.
- Ratings bị loại khỏi RAG corpus vì là dữ liệu recommender interaction.

Lưu ý phản biện: đây là corpus MVP, không phải clinical benchmark. Các tài liệu seed InBody/safety là tri thức được curate từ nguồn công khai và policy nội bộ để lấp khoảng trống dữ liệu cho demo; khi làm đánh giá học thuật nghiêm túc vẫn cần thêm tập câu hỏi chuẩn, tiêu chí relevance và kiểm chứng chuyên môn.

## Vai trò trong Multi-Agent RAG

Corpus này chủ yếu phục vụ `RAGAgent`:

```text
User question
  -> SupervisorAgent
  -> RAGAgent
  -> hybrid_search / rerank
  -> retrieved_docs
  -> ResponseComposerAgent
```

Các agent khác như `InBodyAgent`, `NutritionAgent`, `TrainingAgent` có thể dùng health tools trực tiếp; khi câu hỏi cần kiến thức nền hoặc giải thích sâu, `SupervisorAgent` chọn thêm `RAGAgent`.

## Giới hạn hiện tại

- Chưa có benchmark set riêng cho retrieval quality.
- Chưa có InBody OCR sample dataset chính thức.
- Chưa có dataset public lớn, sạch và chuẩn hóa riêng cho PBF/SMM/BFM/visceral fat bằng tiếng Việt.
- Một phần lớn nutrition corpus đến từ món ăn/food database, cần kiểm soát nhiễu khi truy xuất.
- Dữ liệu PDF phụ thuộc chất lượng `pypdf.extract_text`.

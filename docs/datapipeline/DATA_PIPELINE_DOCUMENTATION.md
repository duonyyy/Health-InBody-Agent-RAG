# Data Pipeline Architecture Documentation - Health/InBody Agent RAG

## 1. Tổng quan Kiến trúc

Trong hệ thống **Health/InBody Multi-Agent RAG**, module `data_pipeline/` đóng vai trò là xương sống xử lý dữ liệu offline (Offline Data Processing). Kiến trúc của hệ thống tuân thủ nguyên tắc **tách rời hoàn toàn (Decoupling)** và cấu trúc **ETL / Data Engineering Production** giữa:

1. **Chu trình chuẩn bị dữ liệu Offline (`data_pipeline/`)**: Trích xuất PDF, nạp dữ liệu thô (Ingestion Layer), chuẩn hóa Unicode NFC & lọc nhiễu (Processing Layer), phân đoạn có cấu trúc (Structure-Aware, Table-Aware), nhúng vector BGE-M3 và nạp vào Qdrant/BM25 (Indexing Layer).
2. **Chu trình phục vụ truy vấn Online (`backend/`)**: Nhận câu hỏi người dùng, phân tích an toàn y tế (Safety Gate), định tuyến Agent, thực thi tìm kiếm lai (Hybrid Search) kết hợp mở rộng Parent-Child và tổng hợp câu trả lời qua LLM.

Sự phân tách này mang lại lợi ích lớn:
- **Tối ưu tài nguyên GPU 4 GB VRAM**: Việc tính toán vector embedding khối lượng lớn được thực hiện độc lập, không tranh chấp bộ nhớ GPU với LLM phục vụ trực tiếp.
- **Khởi động tức thì (Zero-Latency Cold Start)**: Backend nạp chỉ mục từ vựng qua file snapshot nén (`bm25_snapshot.json.gz`) trong < 100ms thay vì phải tải và tính toán lại toàn bộ văn bản.
- **Tính bất biến và Idempotent**: Việc nạp dữ liệu vào Qdrant sử dụng định danh xác định `UUIDv5(chunk_id)` giúp việc chạy lại pipeline không làm trùng lặp vector hay phát sinh chi phí tính toán dư thừa.

---

## 2. Sơ đồ Luồng Dữ liệu (End-to-End Flow)

```text
+-----------------------------------------------------------------------------------+
|                              DATA PIPELINE OFFLINE                                |
+-----------------------------------------------------------------------------------+
  [PDFs / CSVs / JSONs] (dataset/raw/ + source_manifest.json)
           |
           v
  [Stage 1: Extract] -> src/extractors/pdf_extractor.py 
                        (PyMuPDF + TCVN3 decode + Kerning fix)
           |
           v
  [Stage 2: Build]   -> src/ingestion/raw_loader.py (Nạp & gộp nguồn thô)
                     -> src/processors/corpus_processor.py
                        (Gatekeeping lọc recipes, chuẩn hóa NFC, gắn Medical Seeds)
           |
           v
  [Stage 3: Chunk]   -> src/chunkers/markdown_chunker.py & breadcrumbs.py
                        - Contextual Breadcrumbs Injection
                        - Table-Aware Chunking (Bảo tồn Header & Delimiter row)
                        - Parent-Child Chunking (Sinh metadata: parent_id, parent_content)
           |
     +-----+---------------------------------------+
     |                                             |
     v                                             v
  [Stage 4: Index BM25]                 [Stage 5: Index Qdrant]
  src/indexers/bm25_indexer.py          src/indexers/qdrant_indexer.py
  -> bm25_snapshot.json.gz              -> UUID5 Points + Payload Indexes
     |                                             |
     +---------------------+-----------------------+
                           |
                           v
               [Stage 6: Verify Gate]
               run_verify_stage() (Kiểm tra breadcrumbs, rò rỉ recipe, toàn vẹn BM25)
+-----------------------------------------------------------------------------------+
                           |
                           v
+-----------------------------------------------------------------------------------+
|                               BACKEND ONLINE RAG                                  |
+-----------------------------------------------------------------------------------+
  User Query -> hybrid_search() (BM25 + Qdrant Dense)
                     |
                     v
             [Child Candidates] (Top-k chính xác cao)
                     |
                     v
             expand_parent_documents() (Giải nén parent_content & Deduplicate theo parent_id)
                     |
                     v
             Context gửi vào LLM (Đầy đủ, mạch lạc, không cụt ý)
+-----------------------------------------------------------------------------------+
```

---

## 3. Bảng Phân Tích Chi Tiết File & Hàm

### 3.1. Tầng Nạp dữ liệu thô (`src/ingestion/raw_loader.py`)

| Hàm | Vai trò kỹ thuật |
|---|---|
| `clean_text(value)` | Chuẩn hóa NFC, loại bỏ ký tự điều khiển ẩn và ngắt dòng dư thừa. |
| `compact_parts(parts)` | Hợp nhất các trường thông tin thành một chuỗi văn bản hoàn chỉnh. |
| `read_manifest(raw_dir)` | Đọc cấu hình danh mục nguồn dữ liệu thô `source_manifest.json`. |
| `make_record(...)` | Tạo đối tượng bản ghi theo schema chung của RAG dataset. |
| `merge_foods(...)` / `merge_usda(...)` | Chuyển đổi dữ liệu CSV món ăn và JSON USDA thành bản ghi RAG. |
| `merge_ratings(...)` | Chuyển đổi dữ liệu tương tác ratings của người dùng phục vụ recommender. |
| `merge_pdf_placeholder(...)` | Đọc Markdown đã trích xuất từ PDF hoặc sinh bản ghi chờ. |
| `merge_inbody_medical_knowledge(...)` | Nạp các tài liệu chuyên gia InBody và y tế lâm sàng. |
| `merge_source(...)` | Bộ định tuyến chuyển đổi nguồn theo loại định dạng. |
| `merge_all(raw_dir, out, report)` | Hợp nhất toàn bộ nguồn dữ liệu khai báo trong manifest thành tệp `all_raw_sources.jsonl`. |

### 3.2. Tầng Xử lý & Kiểm soát chất lượng (`src/processors/corpus_processor.py`)

| Hàm | Vai trò kỹ thuật |
|---|---|
| `load_jsonl(path)` | Generator đọc file JSON Lines tuần tự tiết kiệm RAM khi xử lý tập dữ liệu lớn. |
| `normalize_document(record)` | Cổng kiểm soát chất lượng (Quality Gate), lọc sạch recipes, ratings và các chuỗi quá ngắn (< 40 ký tự). |
| `seed_document(record)` | Đóng gói bộ tri thức hạt giống an toàn y tế và chỉ số InBody cốt lõi (tier guideline, review approved). |
| `prepare_dataset(input, out, report)` | Kết hợp hạt giống tri thức và dữ liệu chuẩn hóa tạo tệp `embedding_documents.jsonl`. |

### 3.3. Tầng Phân đoạn tri thức (`src/chunkers/`)

| File | Hàm | Vai trò kỹ thuật |
|---|---|---|
| `breadcrumbs.py` | `format_breadcrumb(doc_title, section_hierarchy)` | Tạo chuỗi breadcrumb phân cấp: `[Tài liệu: ... > Chương ... > Mục ...]`. |
| `breadcrumbs.py` | `inject_breadcrumb(content, breadcrumb)` | Chèn chuỗi breadcrumb vào đầu chunk văn bản trước khi embedding. |
| `markdown_chunker.py` | `normalize_chunk_text(text)` | Làm sạch khoảng trắng thừa, xóa dòng trống trùng lặp. |
| `markdown_chunker.py` | `is_table_separator(line)` | Nhận diện dòng gạch ngang phân cách tiêu đề bảng Markdown (`\|---\|---\|`). |
| `markdown_chunker.py` | `extract_content_blocks(content)` | Tách biệt các đoạn văn bản thường và các khối bảng biểu Markdown. |
| `markdown_chunker.py` | `split_markdown_table_with_header(table_text, max_chars, overlap_rows)` | **Cốt lõi:** Cắt nhỏ bảng biểu dài, tự động sao chép Header row và Delimiter row vào đầu mỗi chunk con sinh ra. |
| `markdown_chunker.py` | `split_section_content_table_aware(content, ...)` | Cắt nhỏ nội dung kết hợp văn bản và bảng biểu mà không phá vỡ cấu trúc bảng. |
| `markdown_chunker.py` | `parse_markdown_sections(markdown_text)` | Phân tích cú pháp Markdown thành cây phân cấp section theo heading `#`, `##`, `###`. |
| `markdown_chunker.py` | `chunk_document(doc, ...)` | Điều phối băm toàn bộ tài liệu, tích hợp Breadcrumbs, Table-Aware và gắn metadata Parent-Child. |

### 3.4. Tầng Lưu trữ & Nạp chỉ mục (`src/indexers/`)

| File | Hàm / Phương thức | Vai trò kỹ thuật |
|---|---|---|
| `bm25_indexer.py` | `build_bm25_documents_from_chunks(chunks)` | Chuẩn hóa token, lọc độ dài và xây dựng danh sách document metadata cho BM25. |
| `bm25_indexer.py` | `export_bm25_snapshot(chunks, output_path, ...)` | Đóng gói toàn bộ tập corpus vào tệp nén `bm25_snapshot.json.gz` cho backend. |
| `qdrant_indexer.py` | `QdrantIndexer.is_available()` | Kiểm tra kết nối mạng tới Qdrant server qua HTTP `/readyz`. |
| `qdrant_indexer.py` | `QdrantIndexer.create_collection_if_missing(name)` | Tự động tạo collection vector với khoảng cách Cosine, kích thước 1024 chiều. |
| `qdrant_indexer.py` | `QdrantIndexer.ensure_payload_indexes(name)` | Tạo payload index keyword cho: `content_type`, `domain`, `source`, `parent_id`, `has_parent`. |
| `qdrant_indexer.py` | `QdrantIndexer.get_existing_point_ids(name, ids)` | Lấy danh sách ID điểm đã tồn tại trên server để kích hoạt cơ chế skip (Idempotent). |
| `qdrant_indexer.py` | `QdrantIndexer.index_chunks(chunks, embedder, ...)` | Nạp vector và payload theo lô vào Qdrant với UUIDv5 sinh từ `chunk_id`. |

### 3.5. Tầng Trích xuất (`src/extractors/`) & Vector Embedding (`src/embedder/`)

| File | Hàm / Phương thức | Vai trò kỹ thuật |
|---|---|---|
| `pdf_extractor.py` | `decode_tcvn3(text)` | Giải mã bảng mã TCVN3 sang Unicode NFC cho bảng thực phẩm Việt Nam cũ. |
| `pdf_extractor.py` | `extract_smart_lines(page)` | Trích xuất dòng văn bản từ PDF xử lý lỗi dính từ (kerning fix). |
| `pdf_extractor.py` | `convert_fitness_to_markdown(pdf, out)` | Trích xuất sách fitness sang Markdown giữ nguyên cấu trúc heading. |
| `pdf_extractor.py` | `convert_food_composition_to_markdown(...)` | Trích xuất bảng số liệu thành phần thực phẩm sang bảng biểu Markdown. |
| `client.py` | `EmbeddingClient.embed_texts(texts, batch_size)` | Điều phối chia batch và gửi request embedding tới BGE-M3 service (hỗ trợ dry-run). |
| `client.py` | `EmbeddingClient._mock_vector(text)` | Sinh vector giả lập chuẩn hóa L2 từ hash chuỗi văn bản phục vụ test offline. |

---

## 4. Năm Kỹ Thuật Đột Phá Trong Data Pipeline

### 4.1. Table-Aware Chunking (Bảo tồn Bảng biểu)
- **Hạn chế cũ:** Các bảng đối chiếu thể hình (như bảng chuẩn BMI WPRO, bảng tỷ lệ mỡ PBF) khi dài hơn 600 ký tự sẽ bị cắt ngang giữa bảng, làm các chunk phía sau mất hoàn toàn dòng tiêu đề (Header row), biến dữ liệu số thành vô nghĩa.
- **Giải pháp:** Khi một khối bảng biểu Markdown bị tràn quá giới hạn ký tự, hàm `split_markdown_table_with_header` sẽ:
  1. Trích xuất dòng Header (hàng 0) và dòng Delimiter (hàng 1, dạng `|---|---|`).
  2. Gom các dòng dữ liệu (data rows) thành từng chunk nhỏ.
  3. Tự động đính kèm cặp Header + Delimiter vào đầu mỗi chunk con sinh ra.
  4. Hỗ trợ overlap các hàng dữ liệu (`overlap_rows = 1`) để giữ tính liên tục.

### 4.2. Parent-Child Retrieval (Small-to-Big Retrieval)
- **Hạn chế cũ:** Chunk 600 ký tự quá ngắn để trả lời các câu hỏi tổng hợp, so sánh hoặc yêu cầu lịch tập nguyên tuần, dễ dẫn đến hiện tượng hallucination hoặc buộc phải tăng Top-k gây chậm TTFT.
- **Giải pháp:**
  - Tại bước chunking: Tạo ra các **Child Chunks** nhỏ (400-600 ký tự) gắn kèm trường `parent_id`, `parent_title` và `parent_content` (1500-2500 ký tự chứa trọn vẹn ngữ cảnh của đề mục cha).
  - Tại bước truy vấn online: Tìm kiếm vector và BM25 chạy trên các Child Chunks để có độ khớp từ khóa và ngữ nghĩa cao nhất.
  - Hàm `expand_parent_documents()` tại `backend/src/rag/search.py` giải nén `parent_content` và **khử trùng lặp (deduplicate)** theo `parent_id`. Kết quả là LLM nhận được ngữ cảnh hoàn chỉnh, không bị phân mảnh.

### 4.3. Contextual Breadcrumbs
Mỗi chunk được gán định danh vị trí:
`[Tài liệu: Bảng thành phần thực phẩm Việt Nam > Nhóm: Thịt và sản phẩm chế biến > Mục: Thịt bò bắp]`
Giúp vector embedding định vị chính xác ngữ cảnh ngay cả khi nội dung đoạn văn chỉ chứa các con số rời rạc.

### 4.4. BM25 Zero-Overhead Snapshot
Tập corpus sau khi chunk được lập chỉ mục sẵn và nén thành `backend/data/generated/bm25_snapshot.json.gz` (~930 KB). Backend nạp thẳng snapshot này vào RAM trong < 100ms khi container khởi động, loại bỏ hoàn toàn việc cuộn dữ liệu từ database qua mạng.

### 4.5. Idempotent Qdrant Indexer
- Điểm vector được gán ID bằng `UUID5(NAMESPACE_URL, chunk_id)` giúp việc nạp lại không bị trùng lặp ID.
- Cơ chế `get_existing_point_ids` kiểm tra các điểm đã có để bỏ qua (skip), tiết kiệm 100% thời gian embedding cho dữ liệu không thay đổi.
- Hỗ trợ chế độ `--dry-run` tự sinh vector giả lập chuẩn hóa L2 giúp chạy CI/CD và kiểm thử cục bộ không cần cụm GPU/Qdrant thật.

---

## 5. Schema Hợp đồng Dữ liệu (Data Contract)

Mỗi bản ghi trong `chunks.jsonl` và Qdrant Payload tuân thủ cấu trúc sau:

```json
{
  "chunk_id": "fitness_training_page_0012_chunk_0001",
  "doc_id": "fitness_training_document_page_0012",
  "title": "Kỹ thuật Squat đúng biên độ",
  "content": "[Tài liệu: Cẩm nang Thể hình > Phần 2: Đùi và Mông > Mục: Kỹ thuật Squat]\nKhi thực hiện động tác squat, giữ lưng thẳng tự nhiên...",
  "breadcrumb": "Tài liệu: Cẩm nang Thể hình > Phần 2: Đùi và Mông > Mục: Kỹ thuật Squat",
  "content_type": "exercise",
  "domain": "health_inbody",
  "language": "vi",
  "section_index": 2,
  "chunk_index": 1,
  "parent_id": "fitness_training_page_0012_section_0002",
  "parent_title": "Kỹ thuật Squat",
  "parent_content": "## Kỹ thuật Squat\nKhi thực hiện động tác squat, giữ lưng thẳng tự nhiên. Hạ hông xuống dưới mức song song nếu khớp gối cho phép...",
  "has_parent": true,
  "metadata": {
    "source_id": "fitness_training_document",
    "page_number": 12,
    "source_name": "Cẩm nang Hướng dẫn Thể hình Toàn diện",
    "publisher": "Clinical Fitness Team",
    "source_tier": "guideline"
  }
}
```

---

## 6. Hướng Dẫn Vận Hành & Kiểm Thử

### 6.1. Lệnh Thực Thi Pipeline

```bash
# Thực thi toàn bộ chu trình 6 giai đoạn:
python data_pipeline/run_pipeline.py --all

# Hoặc thực thi từng giai đoạn mong muốn:
python data_pipeline/run_pipeline.py --build
python data_pipeline/run_pipeline.py --chunk
python data_pipeline/run_pipeline.py --index-bm25
python data_pipeline/run_pipeline.py --verify
```

### 6.2. Lệnh Chạy Kiểm Thử Tự Động

```powershell
$env:PYTHONPATH="backend/src;data_pipeline"
python -m pytest data_pipeline/tests backend/tests/unit -v -p no:cacheprovider
```

Kết quả nghiệm thu:
- **148 / 148 tests passed** (Bao gồm unit tests pipeline, table chunking, parent expansion, raw loader, corpus processor và hybrid search).
- Cổng kiểm soát chất lượng đạt chuẩn: **0 rò rỉ recipe**, **100% chunks có breadcrumbs**, **100% khớp snapshot BM25**.

# Data Pipeline - Health/InBody Multi-Agent RAG

Thư mục `data_pipeline/` phụ trách toàn bộ chu trình **trích xuất dữ liệu thô, nạp dữ liệu (Ingestion), làm sạch và kiểm soát chất lượng (Processing), phân đoạn cấu trúc nâng cao (Table-Aware & Parent-Child) và nạp chỉ mục offline (Indexing)** cho hệ thống Health/InBody Agent RAG.

Kiến trúc tuân thủ chuẩn **ETL / Data Engineering Production**, tách rời hoàn toàn giữa **xử lý dữ liệu offline** (`data_pipeline/`) và **phục vụ truy vấn online** (`backend/`) nhằm đảm bảo tính ổn định, tối ưu tài nguyên phần cứng (GPU 4 GB VRAM) và tăng tốc thời gian phản hồi (TTFT) của Agent.

---

## 1. Cấu trúc thư mục & Vai trò các thành phần

```text
data_pipeline/
├── README.md                          # Tài liệu kỹ thuật chi tiết của data pipeline
├── run_pipeline.py                    # CLI điều phối (Orchestrator) 6 giai đoạn end-to-end
├── configs/
│   └── pipeline_config.py             # Cấu hình tập trung (đường dẫn, siêu tham số, endpoint)
├── dataset/
│   ├── raw/                           # Dữ liệu gốc bất biến kèm source_manifest.json
│   ├── processed/                     # Dữ liệu làm sạch, text trích xuất, snapshot BM25
│   ├── chunks/                        # chunks.jsonl (Dữ liệu đã băm với breadcrumbs & parent-child)
│   └── rag_documents/                 # health_inbody_corpus.jsonl (Corpus chuẩn hóa dùng chung)
├── src/
│   ├── extractors/
│   │   └── pdf_extractor.py           # Trích xuất PDF sang Markdown (PyMuPDF + giải mã TCVN3)
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── raw_loader.py              # Đọc và hợp nhất các nguồn thô thành all_raw_sources.jsonl
│   ├── processors/
│   │   ├── __init__.py
│   │   └── corpus_processor.py        # Gatekeeping lọc nhiễu, gắn seed y tế tạo embedding_documents.jsonl
│   ├── chunkers/
│   │   ├── breadcrumbs.py             # Bộ chèn ngữ cảnh phân cấp (Contextual Breadcrumbs)
│   │   └── markdown_chunker.py        # Phân đoạn Table-Aware & Parent-Child Markdown
│   ├── embedder/
│   │   └── client.py                  # Client gọi BGE-M3 embedding (hỗ trợ dry-run & batch)
│   └── indexers/
│       ├── bm25_indexer.py            # Tạo và xuất snapshot BM25 nén (Zero-Overhead Gzip)
│       └── qdrant_indexer.py          # Nạp vector vào Qdrant với UUID5 Idempotent
└── tests/
    └── test_data_pipeline.py          # Bộ kiểm thử tự động toàn diện cho data pipeline
```

---

## 2. Chi tiết vai trò các file và hàm chính

### 2.1. Bộ điều phối (`run_pipeline.py`)
File điều phối trung tâm cho phép chạy từng công đoạn độc lập hoặc liên hoàn toàn bộ:
- `load_jsonl(path)`: **Vai trò:** Cung cấp hàm tiện ích nạp các tệp dataset trung gian dưới dạng danh sách từ điển Python.
- `save_jsonl(records, path)`: **Vai trò:** Lưu trữ an toàn các kết quả xử lý (chunks, documents) vào ổ đĩa chuẩn mã hóa UTF-8.
- `run_extract_stage()`: **Vai trò:** Thực thi Stage 1 - Quét PDF thô, giải mã font TCVN3 và chuyển đổi sang Markdown cấu trúc.
- `run_build_stage()`: **Vai trò:** Thực thi Stage 2 - Hợp nhất nguồn thô qua `raw_loader`, lọc bỏ công thức nấu ăn nhiễu, gắn tri thức hạt giống InBody/y tế chuẩn qua `corpus_processor`.
- `run_chunk_stage()`: **Vai trò:** Thực thi Stage 3 - Phân đoạn Markdown theo heading, bảo toàn bảng biểu và gán quan hệ Parent-Child.
- `run_bm25_stage()`: **Vai trò:** Thực thi Stage 4 - Tính toán chỉ mục từ vựng và xuất file `bm25_snapshot.json.gz` nén.
- `run_qdrant_stage(dry_run)`: **Vai trò:** Thực thi Stage 5 - Chuyển hóa văn bản sang vector BGE-M3 và nạp vào Qdrant theo cơ chế Idempotent.
- `run_verify_stage()`: **Vai trò:** Thực thi Stage 6 - Tự động kiểm thử cổng chất lượng dữ liệu (Quality Gate), phát hiện rò rỉ dữ liệu hoặc sai lệch số lượng.
- `main()`: **Vai trò:** Điểm vào CLI tiếp nhận cờ dòng lệnh (`--all`, `--extract`, `--build`, `--chunk`, `--index-bm25`, `--index-qdrant`, `--verify`, `--dry-run`).

### 2.2. Trích xuất tài liệu (`src/extractors/pdf_extractor.py`)
- `decode_tcvn3(text)`: **Vai trò:** Giải mã chuỗi ký tự bảng mã TCVN3 (ABC) sang Unicode chuẩn cho các tài liệu bảng thành phần thực phẩm VN cũ.
- `get_food_group_name(group_code)`: **Vai trò:** Tra cứu tên nhóm thực phẩm chuẩn từ mã phân loại.
- `extract_smart_lines(page)`: **Vai trò:** Trích xuất dòng văn bản với kỹ thuật xử lý kerning nâng cao, ngăn ngừa hiện tượng dính từ trong PDF.
- `convert_fitness_to_markdown(pdf_path, output_path)`: **Vai trò:** Bóc tách sách thể hình/fitness sang Markdown có cấu trúc phân cấp `#`, `##`.
- `parse_food_table(page, page_number)`: **Vai trò:** Bóc tách dữ liệu dạng bảng số liệu dinh dưỡng từ các trang PDF.
- `convert_food_composition_to_markdown(...)`: **Vai trò:** Chuyển đổi bảng thành phần thực phẩm Việt Nam thành các bảng biểu Markdown chuẩn xác.
- `extract_pdf_to_markdown(raw_dir, output_dir)`: **Vai trò:** Hàm điều phối quét toàn bộ thư mục PDF thô và trích xuất đồng loạt.

### 2.3. Tầng Nạp dữ liệu thô (`src/ingestion/raw_loader.py`)
- `clean_text(value)`: **Vai trò:** Làm sạch chuẩn hóa khoảng trắng, Unicode NFC, loại bỏ ký tự ngắt dòng thừa và ký tự điều khiển ẩn.
- `compact_parts(parts)`: **Vai trò:** Nối các trường thông tin thành một chuỗi văn bản hoàn chỉnh.
- `read_manifest(raw_dir)`: **Vai trò:** Đọc tệp kê khai danh mục nguồn dữ liệu thô `source_manifest.json`.
- `make_record(...)`: **Vai trò:** Tạo bản ghi dữ liệu chuẩn theo schema thống nhất của pipeline.
- `merge_foods(source, raw_dir)`: **Vai trò:** Đọc CSV món ăn, chuẩn hóa dinh dưỡng (calo, fat, protein, carbs).
- `merge_ratings(source, raw_dir)`: **Vai trò:** Đọc dữ liệu tương tác ratings của người dùng phục vụ recommender.
- `nutrient_map(food)`: **Vai trò:** Ánh xạ các chất dinh dưỡng từ đối tượng USDA Foundation Foods.
- `merge_usda(source, raw_dir)`: **Vai trò:** Chuyển đổi dữ liệu chuẩn quốc tế USDA sang bản ghi RAG.
- `merge_pdf_placeholder(source, raw_dir)`: **Vai trò:** Đọc Markdown đã trích xuất từ PDF hoặc tạo bản ghi chờ.
- `merge_inbody_medical_knowledge(source, raw_dir)`: **Vai trò:** Hợp nhất tri thức y khoa lâm sàng và InBody từ tệp JSON.
- `merge_source(source, raw_dir)`: **Vai trò:** Bộ định tuyến chuyển đổi nguồn theo định dạng tệp.
- `merge_all(raw_dir, output_path, report_path)`: **Vai trò:** Hợp nhất toàn bộ nguồn dữ liệu thô thành tệp `all_raw_sources.jsonl`.

### 2.4. Tầng Xử lý & Kiểm soát chất lượng (`src/processors/corpus_processor.py`)
- `load_jsonl(path)`: **Vai trò:** Generator đọc file JSON Lines tuần tự tiết kiệm RAM.
- `normalize_document(record)`: **Vai trò (Quality Gatekeeper):** Lọc bỏ công thức nấu ăn (recipes), ratings, kiểm tra độ dài tối thiểu và chuẩn hóa Unicode NFC.
- `seed_document(record)`: **Vai trò:** Đóng gói các tài liệu tri thức hạt giống an toàn y tế và chỉ số InBody cốt lõi (tier guideline, review approved).
- `prepare_dataset(input_path, output_path, report_path)`: **Vai trò:** Kết hợp hạt giống tri thức và dữ liệu chuẩn hóa tạo tệp `embedding_documents.jsonl`.

### 2.5. Phân đoạn tri thức nâng cao (`src/chunkers/`)
#### `markdown_chunker.py`
- `normalize_chunk_text(text)`: **Vai trò:** Làm sạch chuẩn hóa khoảng trắng và dòng trống trong văn bản chunk.
- `is_table_separator(line)`: **Vai trò:** Nhận diện dòng phân cách tiêu đề bảng Markdown (ví dụ: `|---|---|`).
- `extract_content_blocks(content)`: **Vai trò:** Tách riêng các khối văn bản tự do và các khối bảng biểu Markdown trong một phân đoạn.
- `split_markdown_table_with_header(table_text, max_chars, overlap_rows)`: **Vai trò (Cốt lõi):** Chia nhỏ bảng Markdown dài thành các phần nhỏ mà **luôn nhân bản dòng Header và Delimiter row** ở đầu mỗi chunk con, ngăn chặn mất thông tin cột.
- `split_section_content_table_aware(content, chunk_size, chunk_overlap, ...)`: **Vai trò:** Cắt nhỏ nội dung kết hợp giữa văn bản thường và các khối bảng biểu được bảo toàn.
- `parse_markdown_sections(markdown_text)`: **Vai trò:** Phân tích cú pháp Markdown thành cây phân cấp các section theo tiêu đề `#`, `##`, `###`.
- `chunk_document(doc, chunk_size, chunk_overlap, ...)`: **Vai trò:** Phân đoạn tài liệu RAG hoàn chỉnh: tích hợp Contextual Breadcrumbs, Table-Aware Chunking và sinh metadata **Parent-Child** (`parent_id`, `parent_title`, `parent_content`, `has_parent`).

#### `breadcrumbs.py`
- `format_breadcrumb(doc_title, section_hierarchy)`: **Vai trò:** Định dạng chuỗi định danh phân cấp đường dẫn: `[Tài liệu: ... > Chương ... > Mục ...]`.
- `inject_breadcrumb(content, breadcrumb)`: **Vai trò:** Gắn chuỗi ngữ cảnh vào đầu nội dung chunk phục vụ truy xuất vector chính xác.

### 2.6. Lưu trữ & Nạp chỉ mục (`src/indexers/`)
#### `bm25_indexer.py`
- `build_bm25_documents_from_chunks(chunks)`: **Vai trò:** Chuẩn hóa token, lọc độ dài và xây dựng danh sách document metadata cho BM25.
- `export_bm25_snapshot(chunks, output_path, ...)`: **Vai trò:** Đóng gói toàn bộ tập corpus vào tệp nén `bm25_snapshot.json.gz` (schema v1) để backend khởi động zero-latency (< 100ms).

#### `qdrant_indexer.py` (`QdrantIndexer`)
- `is_available()`: **Vai trò:** Kiểm tra trạng thái trực tuyến của cụm máy chủ Qdrant.
- `create_collection_if_missing(collection_name)`: **Vai trò:** Tự động tạo vector collection với khoảng cách Cosine và kích thước vector 1024 chiều.
- `ensure_payload_indexes(collection_name)`: **Vai trò:** Tạo chỉ mục payload (Keyword) trên các trường: `content_type`, `domain`, `source`, `parent_id`, `has_parent`.
- `get_existing_point_ids(collection_name, point_ids)`: **Vai trò:** Truy vấn danh sách các ID điểm vector đã tồn tại trên Qdrant để hỗ trợ bỏ qua (skip), bảo đảm tính Idempotent.
- `index_chunks(chunks, embedder, ...)`: **Vai trò:** Thực hiện nạp theo batch các vector và metadata vào Qdrant với ID cố định sinh bằng `UUID5(chunk_id)`.

### 2.7. Tạo vector Embedding (`src/embedder/client.py`)
- `is_available()`: **Vai trò:** Kiểm tra trạng thái sẵn sàng của dịch vụ BGE-M3 embedding qua HTTP `/health`.
- `embed_batch(texts)`: **Vai trò:** Gửi lô văn bản tới endpoint embedding để nhận mảng vector thực tế.
- `embed_texts(texts, batch_size)`: **Vai trò:** Điều phối chia lô văn bản và thu thập vector kết quả, tự động fallback sang vector giả lập khi ở chế độ dry-run.
- `_mock_vector(text)`: **Vai trò:** Sinh vector xác định chuẩn hóa L2 từ hash văn bản phục vụ kiểm thử đơn vị hoặc dry-run mà không cần GPU.

---

## 3. Các cơ chế nâng cao đã triển khai

### 3.1. Table-Aware Chunking (Bảo toàn bảng biểu Markdown)
- **Vấn đề giải quyết:** Các bảng đối chiếu thể hình (khoảng phân loại BMI, chuẩn mỡ PBF, bảng calo) nếu bị cắt ngang bởi thuật toán cắt văn bản thông thường sẽ làm mất dòng tiêu đề (Header row), khiến dữ liệu số ở các chunk sau trở thành các dòng vô nghĩa.
- **Giải pháp:** Khi một bảng Markdown vượt quá giới hạn ký tự, thuật toán tự động trích xuất `Header row` và `Delimiter row` (`|---|---|`), sau đó gắn lặp lại ở đầu mỗi chunk con sinh ra từ bảng đó.

### 3.2. Parent-Child Retrieval (Small-to-Big Retrieval & Deduplication)
- **Vấn đề giải quyết:** Chunk nhỏ (400-600 ký tự) rất tối ưu cho tìm kiếm vector và từ khóa chính xác, nhưng quá ngắn để LLM tổng hợp các câu hỏi rộng hoặc so sánh.
- **Giải pháp:**
  - Trong quá trình chunking, mỗi chunk con (`child_chunk`) mang theo toàn bộ nội dung của đề mục cha (`parent_content`, 1500-2500 ký tự) cùng `parent_id`.
  - Khi người dùng hỏi, backend thực hiện Hybrid Search trên các child chunk. Hàm `expand_parent_documents()` tại `backend/src/rag/search.py` sẽ tự động giải nén child chunk thành `parent_content` và **khử trùng lặp (deduplicate)** theo `parent_id`, giúp ngữ cảnh gửi vào LLM luôn đầy đủ và súc tích nhất.

### 3.3. Contextual Breadcrumbs
- Mọi chunk đều được gắn tiền tố điều hướng:
  `[Tài liệu: Cẩm nang Thể hình > Phần 2: Hướng dẫn kỹ thuật > Bài tập: Squat đúng kỹ thuật]`
- Tránh việc mô hình nhầm lẫn ngữ cảnh của các đoạn trích dẫn ngắn khi truy xuất độc lập.

### 3.4. BM25 Zero-Overhead Snapshot
- Toàn bộ 4,405 chunks được build sẵn chỉ mục và xuất bản thành file nén `backend/data/generated/bm25_snapshot.json.gz` (~930 KB).
- Backend khi khởi động chỉ cần nạp tệp snapshot trong < 100ms, không cần cuộn dữ liệu từ database vector hay tiêu tốn thời gian xây dựng lại chỉ mục từ đầu.

---

## 4. Hướng dẫn sử dụng CLI (`run_pipeline.py`)

Chạy từ thư mục gốc của dự án:

```bash
# 1. Chạy toàn bộ chu trình end-to-end:
python data_pipeline/run_pipeline.py --all

# 2. Chạy từng giai đoạn độc lập:
# Stage 1: Trích xuất PDF sang Markdown
python data_pipeline/run_pipeline.py --extract

# Stage 2: Hợp nhất nguồn và chuẩn hóa RAG Corpus
python data_pipeline/run_pipeline.py --build

# Stage 3: Phân đoạn Markdown (Table-Aware & Parent-Child)
python data_pipeline/run_pipeline.py --chunk

# Stage 4: Xuất bản snapshot BM25 nén
python data_pipeline/run_pipeline.py --index-bm25

# Stage 5: Nạp vector vào Qdrant (dùng --dry-run nếu kiểm thử offline)
python data_pipeline/run_pipeline.py --index-qdrant --dry-run

# Stage 6: Kiểm thử tự động cổng chất lượng dữ liệu
python data_pipeline/run_pipeline.py --verify
```

---

## 5. Kiểm thử chất lượng (Quality Gates)

Chạy bộ kiểm thử đơn vị và tích hợp:

```powershell
$env:PYTHONPATH="backend/src;data_pipeline"
python -m pytest data_pipeline/tests backend/tests/unit -v -p no:cacheprovider
```

Kết quả nghiệm thu:
- **148/148 tests passed** (Bao gồm unit tests pipeline, table chunking, parent expansion, raw loader, corpus processor và hybrid search).
- Tỷ lệ bảo tồn Breadcrumbs: **100% (4,405/4,405 chunks)**.
- Tỷ lệ rò rỉ công thức nấu ăn vào RAG: **0 chunk**.
- Toàn vẹn snapshot BM25 so với Qdrant points: **Khớp 100% (4,405 documents)**.

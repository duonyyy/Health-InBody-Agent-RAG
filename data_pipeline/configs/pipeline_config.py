"""Cấu hình Tập trung cho Data Pipeline (Pipeline Configuration).

Vai trò:
    Quản lý tập trung toàn bộ đường dẫn thư mục, file artifacts, các hằng số siêu tham số
    cho quá trình phân đoạn (chunk_size, chunk_overlap), quy chuẩn domain và kết nối Qdrant/Embedding.
    Đảm bảo việc tiền xử lý offline (`data_pipeline/`) hoàn toàn tách rời và độc lập
    với backend runtime (`backend/`).
"""

from __future__ import annotations

import os
from pathlib import Path

# Thư mục gốc dự án
DATA_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DATA_PIPELINE_ROOT.parent

# Các phân vùng thư mục dữ liệu
RAW_DIR = DATA_PIPELINE_ROOT / "dataset" / "raw"
PROCESSED_DIR = DATA_PIPELINE_ROOT / "dataset" / "processed"
CHUNKS_DIR = DATA_PIPELINE_ROOT / "dataset" / "chunks"
RAG_DOCUMENTS_DIR = DATA_PIPELINE_ROOT / "dataset" / "rag_documents"
EXTRACTED_TEXT_DIR = PROCESSED_DIR / "extracted_text"

# File artifacts kết quả
ALL_RAW_SOURCES_PATH = PROCESSED_DIR / "all_raw_sources.jsonl"
EMBEDDING_DOCUMENTS_PATH = PROCESSED_DIR / "embedding_documents.jsonl"
RAG_CORPUS_PATH = RAG_DOCUMENTS_DIR / "health_inbody_corpus.jsonl"
CHUNKS_PATH = CHUNKS_DIR / "chunks.jsonl"
PIPELINE_REPORT_PATH = PROCESSED_DIR / "pipeline_report.json"

# Đường dẫn đồng bộ artifact snapshot cho Backend (khởi động 0ms overhead)
BACKEND_DATA_DIR = PROJECT_ROOT / "backend" / "data" / "generated"
BACKEND_BM25_SNAPSHOT_PATH = Path(
    os.getenv("BM25_SNAPSHOT_PATH", str(BACKEND_DATA_DIR / "bm25_snapshot.json.gz"))
)

# Quy chuẩn miền và 5 loại nội dung cốt lõi của hệ thống Health/InBody
PROJECT_DOMAIN = "health_inbody"
ALLOWED_CONTENT_TYPES = {
    "nutrition",
    "exercise",
    "inbody_metric",
    "medical_safety",
    "general_health",
}

# Siêu tham số phân đoạn (tối ưu hóa cho ngữ nghĩa Tiếng Việt & mô hình BGE-M3 1024 dims)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
MIN_CHUNK_LENGTH = int(os.getenv("MIN_CHUNK_LENGTH", "60"))
MAX_HEADER_LEVEL = 3

# Cấu hình kết nối Cơ sở dữ liệu Vector Qdrant
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DEFAULT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "nmk_chatbot_active")
DEFAULT_VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "1024"))
DEFAULT_DISTANCE = "Cosine"
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
DEFAULT_TIMEOUT = float(os.getenv("QDRANT_TIMEOUT", "30.0"))

# Cấu hình kết nối Dịch vụ nhúng BGE-M3 Serving
EMBEDDING_API_URL = os.getenv("CUSTOM_EMBEDDING_API_URL", "http://localhost:5001")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
EMBEDDING_TIMEOUT = float(os.getenv("EMBEDDING_TIMEOUT", "30.0"))

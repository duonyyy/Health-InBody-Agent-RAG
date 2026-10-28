"""Master Data Pipeline Orchestrator for Health/InBody Agent RAG.

One-click enterprise pipeline:
1. Extract (PyMuPDF with smart kerning & TCVN3 decoding to Markdown)
2. Build (Clean normalization, RAG gatekeeping, Medical seed integration)
3. Chunk (Structure-aware Markdown & contextual breadcrumb injection)
4. Index BM25 (Direct export of zero-overhead gzip BM25 snapshot for backend)
5. Index Qdrant (Direct vector database batch upsert with UUID5 points)
6. Verify (Automated quality gate verification)

Usage:
    python data_pipeline/run_pipeline.py --all
    python data_pipeline/run_pipeline.py --extract
    python data_pipeline/run_pipeline.py --chunk
    python data_pipeline/run_pipeline.py --index-bm25
    python data_pipeline/run_pipeline.py --index-qdrant [--dry-run]
    python data_pipeline/run_pipeline.py --verify
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to sys.path so configs and src can be imported cleanly
PIPELINE_ROOT = Path(__file__).resolve().parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from configs.pipeline_config import (
    ALL_RAW_SOURCES_PATH,
    ALLOWED_CONTENT_TYPES,
    BACKEND_BM25_SNAPSHOT_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHUNKS_PATH,
    DEFAULT_BATCH_SIZE,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_QDRANT_URL,
    DEFAULT_VECTOR_SIZE,
    EMBEDDING_API_URL,
    EMBEDDING_DOCUMENTS_PATH,
    EXTRACTED_TEXT_DIR,
    MIN_CHUNK_LENGTH,
    PIPELINE_REPORT_PATH,
    RAG_CORPUS_PATH,
    RAW_DIR,
)
from src.chunkers.markdown_chunker import chunk_document
from src.embedder.client import EmbeddingClient
from src.extractors.pdf_extractor import extract_pdf_to_markdown
from src.indexers.bm25_indexer import export_bm25_snapshot
from src.indexers.qdrant_indexer import QdrantIndexer
from src.ingestion.raw_loader import merge_all
from src.processors.corpus_processor import prepare_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("data_pipeline")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Đọc dữ liệu từ file định dạng JSON Lines (.jsonl).

    Vai trò:
        Cung cấp hàm tiện ích nạp các tệp dataset trung gian (raw sources,
        normalized corpus, chunks) dưới dạng danh sách từ điển Python để phục
        vụ quá trình xử lý qua từng giai đoạn của pipeline.

    Args:
        path: Đường dẫn Path trỏ tới file JSONL cần đọc.

    Returns:
        Danh sách các dict chứa dữ liệu từng dòng JSON.
    """
    records = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_jsonl(records: List[Dict[str, Any]], path: Path) -> None:
    """Ghi danh sách bản ghi ra file định dạng JSON Lines (.jsonl).

    Vai trò:
        Lưu trữ an toàn các kết quả xử lý của pipeline (như chunks, documents)
        vào ổ đĩa với mã hóa UTF-8 chuẩn xác, tự động tạo thư mục cha nếu chưa tồn tại.

    Args:
        records: Danh sách bản ghi dict cần tuần tự hóa thành JSON.
        path: Đường dẫn Path tới file đích.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: EXTRACT PDF TO STRUCTURED MARKDOWN
# ─────────────────────────────────────────────────────────────────────────────
def run_extract_stage() -> Dict[str, Any]:
    """Thực thi Stage 1: Trích xuất tài liệu PDF sang định dạng Markdown có cấu trúc.

    Vai trò:
        Giai đoạn đầu vào của pipeline, quét toàn bộ tệp PDF trong thư mục raw,
        xử lý giải mã font TCVN3 (cho bảng thành phần thực phẩm VN), sửa lỗi dính chữ
        (kerning) và xuất ra file Markdown lưu giữ cấu trúc tiêu đề (#, ##) và bảng biểu.

    Returns:
        Dict tổng kết thống kê số trang trích xuất, thời gian thực thi và trạng thái.
    """
    logger.info("=== STAGE 1: Extracting PDFs to Structured Markdown ===")
    start_time = time.time()
    result = extract_pdf_to_markdown(RAW_DIR, EXTRACTED_TEXT_DIR)
    elapsed = round(time.time() - start_time, 2)
    logger.info("Extraction completed in %.2fs: %s", elapsed, result)
    return {"stage": "extract", "elapsed_seconds": elapsed, **result}


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: BUILD & NORMALIZE RAG CORPUS
# ─────────────────────────────────────────────────────────────────────────────
def run_build_stage() -> Dict[str, Any]:
    """Thực thi Stage 2: Hợp nhất các nguồn dữ liệu thô và chuẩn hóa RAG Corpus.

    Vai trò:
        Thực hiện gatekeeping lọc bỏ dữ liệu nhiễu (công thức nấu ăn recipe),
        chuẩn hóa Unicode NFC, tích hợp bộ seed dữ liệu an toàn y tế (medical seeds),
        và đồng bộ corpus tài liệu chuẩn vào thư mục phục vụ indexing.

    Returns:
        Dict chứa số lượng tài liệu chuẩn hóa và thời gian xử lý.
    """
    logger.info("=== STAGE 2: Merging Raw Sources & Normalizing Corpus ===")
    start_time = time.time()
    merge_report = ALL_RAW_SOURCES_PATH.parent / "merge_report.json"
    embedding_report = EMBEDDING_DOCUMENTS_PATH.parent / "embedding_report.json"

    # Merge all raw sources (excluding recipes and non-RAG data)
    merge_all(RAW_DIR, ALL_RAW_SOURCES_PATH, merge_report)

    # Filter and attach medical seeds
    prepare_dataset(ALL_RAW_SOURCES_PATH, EMBEDDING_DOCUMENTS_PATH, embedding_report)

    # Sync copy to rag_documents
    RAG_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAG_CORPUS_PATH.write_bytes(EMBEDDING_DOCUMENTS_PATH.read_bytes())

    docs = load_jsonl(EMBEDDING_DOCUMENTS_PATH)
    elapsed = round(time.time() - start_time, 2)
    logger.info(
        "Corpus build completed in %.2fs: %s high-precision documents",
        elapsed,
        len(docs),
    )
    return {
        "stage": "build",
        "elapsed_seconds": elapsed,
        "document_count": len(docs),
        "corpus_path": str(EMBEDDING_DOCUMENTS_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3: STRUCTURE-AWARE CHUNKING WITH BREADCRUMBS
# ─────────────────────────────────────────────────────────────────────────────
def run_chunk_stage() -> Dict[str, Any]:
    """Thực thi Stage 3: Phân đoạn tài liệu theo cấu trúc kết hợp Contextual Breadcrumbs.

    Vai trò:
        Cắt nhỏ tài liệu theo cấu trúc heading Markdown, gắn định danh phân cấp
        (breadcrumbs) vào đầu chunk để tránh mất ngữ cảnh. Áp dụng Table-Aware Chunking
        để bảo tồn header bảng biểu và Parent-Child Chunking hỗ trợ Small-to-Big Retrieval.

    Returns:
        Dict thống kê số lượng chunk sinh ra phân loại theo content_type và thời gian thực thi.
    """
    logger.info("=== STAGE 3: Structure-Aware Chunking with Contextual Breadcrumbs ===")
    start_time = time.time()
    docs = load_jsonl(EMBEDDING_DOCUMENTS_PATH)
    if not docs:
        raise RuntimeError(f"Corpus {EMBEDDING_DOCUMENTS_PATH} is empty. Run build first.")

    all_chunks: List[Dict[str, Any]] = []
    type_counts: Dict[str, int] = {}

    for doc in docs:
        chunks = chunk_document(
            doc,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            min_chunk_length=MIN_CHUNK_LENGTH,
        )
        for c in chunks:
            all_chunks.append(c)
            ct = c.get("content_type", "unknown")
            type_counts[ct] = type_counts.get(ct, 0) + 1

    save_jsonl(all_chunks, CHUNKS_PATH)
    elapsed = round(time.time() - start_time, 2)
    logger.info(
        "Chunking completed in %.2fs: %s documents -> %s chunks",
        elapsed,
        len(docs),
        len(all_chunks),
    )
    return {
        "stage": "chunk",
        "elapsed_seconds": elapsed,
        "input_documents": len(docs),
        "total_chunks": len(all_chunks),
        "type_counts": type_counts,
        "output_path": str(CHUNKS_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4: EXPORT ZERO-OVERHEAD BM25 SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────
def run_bm25_stage() -> Dict[str, Any]:
    """Thực thi Stage 4: Xây dựng và xuất bản snapshot BM25 nén (Zero-Overhead).

    Vai trò:
        Sinh artifact `bm25_snapshot.json.gz` cho backend RAG hybrid search. Lưu sẵn
        tần số từ, độ dài văn bản và IDF để backend khởi động tức thì trong < 100ms
        mà không phải tính toán lại chỉ mục BM25 trong bộ nhớ.

    Returns:
        Dict chứa kết quả xuất snapshot cho backend và bản lưu trữ trong data pipeline.
    """
    logger.info("=== STAGE 4: Exporting BM25 Snapshot Artifact ===")
    start_time = time.time()
    chunks = load_jsonl(CHUNKS_PATH)
    if not chunks:
        raise RuntimeError(f"Chunks file {CHUNKS_PATH} is empty. Run chunk first.")

    # Export to backend generated snapshot
    res_backend = export_bm25_snapshot(
        chunks=chunks,
        output_path=BACKEND_BM25_SNAPSHOT_PATH,
        collection_name=DEFAULT_COLLECTION_NAME,
        corpus_version="2026.1",
    )

    # Also export copy inside data_pipeline processed dir
    pipeline_copy = CHUNKS_PATH.parent.parent / "processed" / "bm25_snapshot.json.gz"
    res_pipeline = export_bm25_snapshot(
        chunks=chunks,
        output_path=pipeline_copy,
        collection_name=DEFAULT_COLLECTION_NAME,
        corpus_version="2026.1",
    )

    elapsed = round(time.time() - start_time, 2)
    logger.info("BM25 snapshot export completed in %.2fs", elapsed)
    return {
        "stage": "index_bm25",
        "elapsed_seconds": elapsed,
        "backend_snapshot": res_backend,
        "pipeline_snapshot": res_pipeline,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5: DIRECT QDRANT INDEXING
# ─────────────────────────────────────────────────────────────────────────────
def run_qdrant_stage(dry_run: bool = False) -> Dict[str, Any]:
    """Thực thi Stage 5: Đưa vector và payload của chunk vào cơ sở dữ liệu vector Qdrant.

    Vai trò:
        Chuyển hóa văn bản chunk thành vector embedding đa chiều (BGE-M3 1024-d)
        và nạp vào Qdrant theo cơ chế Idempotent Upsert (dùng UUIDv5 từ chunk_id),
        tự động tạo payload index phục vụ bộ lọc tìm kiếm và hỗ trợ chế độ dry-run khi offline.

    Args:
        dry_run: Cờ bật chế độ giả lập kiểm tra tính hợp lệ mà không gọi dịch vụ thật.

    Returns:
        Dict thống kê số vector đã nạp, số điểm bỏ qua, trạng thái kết nối Qdrant/Embedder.
    """
    logger.info("=== STAGE 5: Direct Qdrant Vector Database Indexing ===")
    start_time = time.time()
    chunks = load_jsonl(CHUNKS_PATH)
    if not chunks:
        raise RuntimeError(f"Chunks file {CHUNKS_PATH} is empty. Run chunk first.")

    embedder = EmbeddingClient(
        api_url=EMBEDDING_API_URL,
        vector_size=DEFAULT_VECTOR_SIZE,
    )
    indexer = QdrantIndexer(
        url=DEFAULT_QDRANT_URL,
        vector_size=DEFAULT_VECTOR_SIZE,
    )

    qdrant_online = indexer.is_available()
    embedder_online = embedder.is_available()

    logger.info("Service Status: Qdrant=%s, Embedder=%s", qdrant_online, embedder_online)

    effective_dry_run = dry_run or not (qdrant_online and embedder_online)
    if effective_dry_run and not dry_run:
        logger.warning(
            "Live Qdrant/Embedding service is currently offline. "
            "Executing in DRY-RUN mode to validate payloads and vectors."
        )

    if not effective_dry_run:
        indexer.create_collection_if_missing(DEFAULT_COLLECTION_NAME)

    res = indexer.index_chunks(
        chunks=chunks,
        embedder=embedder,
        collection_name=DEFAULT_COLLECTION_NAME,
        batch_size=DEFAULT_BATCH_SIZE,
        dry_run=effective_dry_run,
    )

    elapsed = round(time.time() - start_time, 2)
    logger.info("Qdrant indexing finished in %.2fs: %s", elapsed, res)
    return {
        "stage": "index_qdrant",
        "elapsed_seconds": elapsed,
        "qdrant_online": qdrant_online,
        "embedder_online": embedder_online,
        "dry_run": effective_dry_run,
        "result": res,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 6: AUTOMATED QUALITY GATE VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
def run_verify_stage() -> Dict[str, Any]:
    """Thực thi Stage 6: Kiểm thử tự động cổng chất lượng dữ liệu (Quality Gate).

    Vai trò:
        Xác thực toàn diện corpus trước khi đưa vào sản xuất: kiểm tra sự tồn tại của breadcrumbs,
        phát hiện rò rỉ công thức nấu ăn vào corpus RAG, kiểm tra kích thước chunk tối thiểu,
        và đảm bảo tính toàn vẹn số lượng văn bản trong snapshot BM25 so với Qdrant chunks.

    Returns:
        Dict kết quả kiểm thử (passed: bool), chi tiết các lỗi phát hiện (nếu có).
    """
    logger.info("=== STAGE 6: Automated Quality Gate Verification ===")
    start_time = time.time()
    chunks = load_jsonl(CHUNKS_PATH)
    errors: List[str] = []

    if not chunks:
        errors.append("chunks.jsonl is missing or empty")

    # Check breadcrumbs and content types
    recipe_in_rag = 0
    missing_breadcrumbs = 0
    short_chunks = 0

    for idx, c in enumerate(chunks, start=1):
        ct = c.get("content_type")
        if ct not in ALLOWED_CONTENT_TYPES:
            errors.append(f"Chunk {idx}: invalid content_type {ct}")
        if ct == "nutrition" and any(w in (c.get("content") or "").lower() for w in ["hầm 45 phút", "muỗng canh"]):
            recipe_in_rag += 1
        if not c.get("breadcrumb"):
            missing_breadcrumbs += 1
        if len(c.get("content") or "") < 40:
            short_chunks += 1

    if recipe_in_rag > 0:
        errors.append(f"Corpus pollution: found {recipe_in_rag} recipe chunks in RAG corpus")
    if missing_breadcrumbs > 0:
        errors.append(f"Found {missing_breadcrumbs} chunks without contextual breadcrumbs")
    if short_chunks > 0:
        errors.append(f"Found {short_chunks} chunks under minimum length threshold")

    # Verify BM25 snapshot integrity
    if not BACKEND_BM25_SNAPSHOT_PATH.exists():
        errors.append(f"BM25 snapshot not found at {BACKEND_BM25_SNAPSHOT_PATH}")
    else:
        try:
            with gzip.open(BACKEND_BM25_SNAPSHOT_PATH, "rt", encoding="utf-8") as f:
                snap = json.load(f)
                if snap.get("schema_version") != 1:
                    errors.append("BM25 snapshot schema_version != 1")
                if len(snap.get("documents", [])) != len(chunks):
                    errors.append(
                        f"BM25 document count mismatch: {len(snap.get('documents', []))} vs {len(chunks)}"
                    )
        except Exception as exc:
            errors.append(f"Failed to read BM25 snapshot: {exc}")

    passed = len(errors) == 0
    elapsed = round(time.time() - start_time, 2)
    logger.info("Verification finished in %.2fs: passed=%s (errors=%s)", elapsed, passed, len(errors))

    return {
        "stage": "verify",
        "passed": passed,
        "elapsed_seconds": elapsed,
        "total_chunks": len(chunks),
        "recipe_chunks_in_rag": recipe_in_rag,
        "missing_breadcrumbs": missing_breadcrumbs,
        "errors": errors[:20],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    """Điểm vào chính (CLI Entrypoint) điều phối toàn bộ luồng Data Pipeline.

    Vai trò:
        Phân tích đối số dòng lệnh CLI, khởi chạy từng giai đoạn độc lập hoặc
        chạy liên hoàn toàn bộ chu trình từ trích xuất thô tới nạp cơ sở dữ liệu
        và xác thực chất lượng, sau đó xuất báo cáo thực thi JSON.
    """
    parser = argparse.ArgumentParser(description="Health/InBody Data Pipeline Orchestrator")
    parser.add_argument("--all", action="store_true", help="Run the entire pipeline end-to-end")
    parser.add_argument("--extract", action="store_true", help="Extract PDFs to Markdown")
    parser.add_argument("--build", action="store_true", help="Merge and normalize raw sources")
    parser.add_argument("--chunk", action="store_true", help="Run structure-aware chunking")
    parser.add_argument("--index-bm25", action="store_true", help="Build and export BM25 snapshot")
    parser.add_argument("--index-qdrant", action="store_true", help="Directly index chunks into Qdrant")
    parser.add_argument("--verify", action="store_true", help="Run quality gate verifications")
    parser.add_argument("--dry-run", action="store_true", help="Simulate Qdrant indexing without live server")

    args = parser.parse_args()

    # Default to running all if no flag provided
    run_all = args.all or not (
        args.extract or args.build or args.chunk or args.index_bm25 or args.index_qdrant or args.verify
    )

    overall_start = time.time()
    report: Dict[str, Any] = {
        "pipeline_version": "2026.1",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stages": {},
    }

    if run_all or args.extract:
        report["stages"]["extract"] = run_extract_stage()

    if run_all or args.build:
        report["stages"]["build"] = run_build_stage()

    if run_all or args.chunk:
        report["stages"]["chunk"] = run_chunk_stage()

    if run_all or args.index_bm25:
        report["stages"]["index_bm25"] = run_bm25_stage()

    if run_all or args.index_qdrant:
        report["stages"]["index_qdrant"] = run_qdrant_stage(dry_run=args.dry_run)

    if run_all or args.verify:
        report["stages"]["verify"] = run_verify_stage()

    report["total_elapsed_seconds"] = round(time.time() - overall_start, 2)
    PIPELINE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("=== Pipeline Execution Finished in %.2fs ===", report["total_elapsed_seconds"])
    logger.info("Report saved to %s", PIPELINE_REPORT_PATH)


if __name__ == "__main__":
    main()

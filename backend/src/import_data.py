"""Import Health/InBody embedding dataset into Qdrant.

Script này dùng corpus đã chuẩn hóa từ `data_pipeline`, mặc định là:

`data_pipeline/dataset/processed/embedding_documents.jsonl`

Mỗi dòng JSONL cần có các field chính: `doc_id`, `title`, `content`,
`source`, `content_type`, `domain`, `language`, `metadata`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).parent))

from utils import setup_logging

try:
    from splitter import split_document as project_split_document
except Exception as exc:
    project_split_document = None
    SPLITTER_IMPORT_ERROR = exc
else:
    SPLITTER_IMPORT_ERROR = None

_fallback_splitter_warned = False

setup_logging()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_FILE = (
    PROJECT_ROOT
    / "data_pipeline"
    / "dataset"
    / "processed"
    / "embedding_documents.jsonl"
)
DEFAULT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "nmk_chatbot_collection")
DEFAULT_VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "1024"))

REQUIRED_FIELDS = {
    "doc_id",
    "title",
    "content",
    "source",
    "content_type",
    "domain",
    "language",
}

ALLOWED_CONTENT_TYPES = {
    "inbody_metric",
    "nutrition",
    "exercise",
    "medical_safety",
    "general_health",
}


class SimpleDocument:
    """Fallback Document tối giản khi môi trường local chưa cài LangChain."""

    def __init__(self, page_content: str, metadata: dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata


def split_document_safe(
    text: str,
    metadata: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Any]:
    """Dùng splitter chính nếu có, fallback theo ký tự khi thiếu dependency local."""
    if project_split_document is not None:
        return project_split_document(
            text,
            metadata=metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    global _fallback_splitter_warned
    if not _fallback_splitter_warned:
        logger.warning(
            "Using fallback splitter because project splitter is unavailable: %s",
            SPLITTER_IMPORT_ERROR,
        )
        _fallback_splitter_warned = True
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return []

    step = max(1, chunk_size - chunk_overlap)
    chunks = []
    for index, start in enumerate(range(0, len(normalized), step), start=1):
        chunk_text = normalized[start : start + chunk_size]
        if not chunk_text.strip():
            continue
        chunk_metadata = {
            **metadata,
            "chunk_index": index,
            "chunk_length": len(chunk_text),
            "fallback_splitter": True,
        }
        chunks.append(SimpleDocument(chunk_text, chunk_metadata))
    chunk_count = len(chunks)
    for chunk in chunks:
        chunk.metadata["chunk_count"] = chunk_count
    return chunks


def get_embedding_safe(text: str) -> list[float]:
    """Lazy import embedding để dry-run không cần đủ backend dependencies."""
    from brain import get_embedding

    return get_embedding(text)


def add_vector_safe(collection_name: str, vectors: dict[str, Any], batch_size: int):
    """Lazy import Qdrant writer."""
    from vectorize import add_vector

    return add_vector(collection_name=collection_name, vectors=vectors, batch_size=batch_size)


def create_collection_safe(collection_name: str, vector_size: int):
    """Lazy import Qdrant collection creator."""
    from vectorize import create_collection

    return create_collection(collection_name, vector_size=vector_size)


def initialize_search_index_safe(documents: list[dict[str, Any]]):
    """Lazy import BM25 search indexer."""
    from search import initialize_search_index

    return initialize_search_index(documents)


def load_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    """Đọc JSONL và trả về `(line_number, record)`."""
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_number, json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc


def validate_document(record: dict[str, Any], line_number: int) -> list[str]:
    """Kiểm tra document có đúng schema embedding của dự án không."""
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(record))
    if missing:
        errors.append(f"line {line_number}: missing fields: {', '.join(missing)}")

    if str(record.get("domain") or "") != "health_inbody":
        errors.append(f"line {line_number}: domain must be health_inbody")

    content_type = record.get("content_type")
    if content_type not in ALLOWED_CONTENT_TYPES:
        errors.append(f"line {line_number}: invalid content_type={content_type}")

    content = str(record.get("content") or "").strip()
    if len(content) < 40:
        errors.append(f"line {line_number}: content too short")

    return errors


def build_chunk_vectors(
    record: dict[str, Any],
    line_number: int,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split một document, tạo embedding cho từng chunk và chuẩn bị payload Qdrant."""
    doc_id = str(record["doc_id"])
    title = str(record.get("title") or "")
    content = str(record.get("content") or "")
    metadata = {
        **(record.get("metadata") or {}),
        "doc_id": doc_id,
        "title": title,
        "source": record.get("source"),
        "content_type": record.get("content_type"),
        "domain": "health_inbody",
        "language": record.get("language", "vi"),
        "line_number": line_number,
    }

    chunks = split_document_safe(
        content,
        metadata=metadata,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    vectors: dict[str, dict[str, Any]] = {}
    for chunk_index, chunk in enumerate(chunks, start=1):
        chunk_id = f"{doc_id}-{chunk_index}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
        vectors[point_id] = {
            "vector": get_embedding_safe(chunk.page_content),
            "payload": {
                **chunk.metadata,
                "chunk_id": chunk_id,
                "question": title,
                "content": chunk.page_content,
                "qdrant_point_id": point_id,
            },
        }

    search_document = {
        "doc_id": doc_id,
        "question": title,
        "title": title,
        "content": content,
        "source": record.get("source"),
        "content_type": record.get("content_type"),
        "domain": "health_inbody",
        "language": record.get("language", "vi"),
    }
    return vectors, search_document


def import_embedding_dataset(
    data_file_path: str | Path = DEFAULT_DATA_FILE,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    batch_size: int = 50,
    limit: int | None = None,
    vector_size: int = DEFAULT_VECTOR_SIZE,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    skip_collection_create: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Import corpus Health/InBody đã chuẩn hóa vào Qdrant.

    `dry_run=True` chỉ validate và đếm document/chunk, không gọi embedding/Qdrant.
    """
    data_path = Path(data_file_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    logger.info("Import dataset: %s", data_path)
    logger.info("Collection: %s", collection_name)
    logger.info("Batch size: %s, limit: %s", batch_size, limit or "none")

    if not dry_run and not skip_collection_create:
        try:
            create_collection_safe(collection_name, vector_size=vector_size)
            logger.info("Created Qdrant collection: %s", collection_name)
        except Exception as exc:
            logger.info("Collection create skipped/failed, continuing: %s", exc)

    vectors_batch: dict[str, dict[str, Any]] = {}
    documents_for_search: list[dict[str, Any]] = []
    counts_by_content_type: dict[str, int] = {}
    processed_docs = 0
    skipped_docs = 0
    error_count = 0
    total_chunks = 0
    validation_errors: list[str] = []

    for record_index, (line_number, record) in enumerate(load_jsonl(data_path)):
        if limit is not None and record_index >= limit:
            break

        errors = validate_document(record, line_number)
        if errors:
            skipped_docs += 1
            error_count += len(errors)
            validation_errors.extend(errors[:5])
            for error in errors:
                logger.warning(error)
            continue

        content_type = str(record["content_type"])
        counts_by_content_type[content_type] = counts_by_content_type.get(content_type, 0) + 1

        try:
            if dry_run:
                chunks = split_document_safe(
                    str(record["content"]),
                    metadata={
                        "doc_id": record["doc_id"],
                        "content_type": record["content_type"],
                        "domain": "health_inbody",
                    },
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                total_chunks += len(chunks)
                processed_docs += 1
                continue

            vectors, search_document = build_chunk_vectors(
                record,
                line_number=line_number,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if not vectors:
                skipped_docs += 1
                logger.warning("line %s: no chunks created", line_number)
                continue

            vectors_batch.update(vectors)
            documents_for_search.append(search_document)
            processed_docs += 1
            total_chunks += len(vectors)

            if len(vectors_batch) >= batch_size:
                add_vector_safe(collection_name=collection_name, vectors=vectors_batch, batch_size=batch_size)
                logger.info(
                    "Upserted batch: %s chunks, processed_docs=%s",
                    len(vectors_batch),
                    processed_docs,
                )
                vectors_batch = {}

        except Exception as exc:
            skipped_docs += 1
            error_count += 1
            logger.exception("line %s: import failed: %s", line_number, exc)

    if vectors_batch and not dry_run:
        add_vector_safe(collection_name=collection_name, vectors=vectors_batch, batch_size=batch_size)
        logger.info("Upserted final batch: %s chunks", len(vectors_batch))

    if documents_for_search and not dry_run:
        initialize_search_index_safe(documents_for_search)
        logger.info("Initialized BM25 search index with %s documents", len(documents_for_search))

    result = {
        "status": error_count == 0,
        "dry_run": dry_run,
        "data_file": str(data_path),
        "collection_name": collection_name,
        "processed_docs": processed_docs,
        "skipped_docs": skipped_docs,
        "total_chunks": total_chunks,
        "counts_by_content_type": counts_by_content_type,
        "error_count": error_count,
        "validation_errors_preview": validation_errors[:20],
    }
    logger.info("Import result: %s", result)
    return result


def import_qa_data(*args, **kwargs):
    """Backward-compatible alias cho code cũ."""
    return import_embedding_dataset(*args, **kwargs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Health/InBody embedding_documents.jsonl into Qdrant"
    )
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--vector-size", type=int, default=DEFAULT_VECTOR_SIZE)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--skip-collection-create", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_embedding_dataset(
        data_file_path=args.data_file,
        collection_name=args.collection,
        batch_size=args.batch_size,
        limit=args.limit,
        vector_size=args.vector_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        skip_collection_create=args.skip_collection_create,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] else 1)


if __name__ == "__main__":
    main()

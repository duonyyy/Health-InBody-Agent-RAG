"""Import Health/InBody embedding dataset into Qdrant.

Script này dùng corpus đã chuẩn hóa từ `data_pipeline`, mặc định là:

`data_pipeline/dataset/processed/embedding_documents.jsonl`

Mỗi dòng JSONL cần có các field chính: `doc_id`, `title`, `content`,
`source`, `content_type`, `domain`, `language`, `metadata`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).parent))

from configs import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CORPUS_VERSION,
    DEFAULT_VECTOR_SIZE,
)
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


class ImportWriteError(RuntimeError):
    """Fatal Qdrant write failure; continuing would report misleading progress."""


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


def get_embedding_safe(
    text: str | list[str],
) -> list[float] | list[list[float]]:
    """Lazy import embedding để dry-run không cần đủ backend dependencies."""
    from brain import get_embedding

    return get_embedding(text)


def add_vector_safe(collection_name: str, vectors: dict[str, Any], batch_size: int):
    """Lazy import Qdrant writer."""
    from vectorize import add_vector

    try:
        return add_vector(
            collection_name=collection_name,
            vectors=vectors,
            batch_size=batch_size,
            raise_on_error=True,
        )
    except Exception as exc:
        raise ImportWriteError(
            f"Qdrant write failed for {len(vectors)} vector(s)"
        ) from exc


def create_collection_safe(collection_name: str, vector_size: int):
    """Lazy import Qdrant collection creator."""
    from vectorize import create_collection

    return create_collection(collection_name, vector_size=vector_size)


def ensure_payload_indexes_safe(collection_name: str):
    """Lazy import Qdrant payload-index setup."""
    from vectorize import ensure_payload_indexes

    return ensure_payload_indexes(collection_name, raise_on_error=True)


def get_collection_point_ids_safe(collection_name: str) -> set[str]:
    """Lazy import point-ID scan used by resumable/missing-only imports."""
    from vectorize import get_collection_point_ids

    return get_collection_point_ids(collection_name)


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


def sha256_file(path: Path) -> str:
    """Return a reproducible checksum for the imported corpus."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_import_manifest(path: Path | None, payload: dict[str, Any]) -> None:
    """Atomically persist import progress/result when a path is configured."""
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary_path.replace(path)


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


def build_chunk_payloads(
    record: dict[str, Any],
    line_number: int,
    chunk_size: int,
    chunk_overlap: int,
    corpus_version: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split one document and build stable point IDs plus canonical payloads."""
    doc_id = str(record["doc_id"])
    title = str(record.get("title") or "")
    content = str(record.get("content") or "")
    metadata = {
        **(record.get("metadata") or {}),
        "doc_id": doc_id,
        "document_id": doc_id,
        "corpus_version": corpus_version,
        "title": title,
        "source": record.get("source"),
        "source_url": record.get("source_url")
        or (record.get("metadata") or {}).get("source_url"),
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

    payloads: dict[str, dict[str, Any]] = {}
    for chunk_index, chunk in enumerate(chunks, start=1):
        chunk_id = f"{doc_id}-{chunk_index}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
        content_hash = hashlib.sha256(
            chunk.page_content.encode("utf-8")
        ).hexdigest()
        payloads[point_id] = {
            **chunk.metadata,
            "chunk_id": chunk_id,
            "question": title,
            "content": chunk.page_content,
            "text": chunk.page_content,
            "content_hash": content_hash,
            "qdrant_point_id": point_id,
        }

    search_document = {
        "doc_id": doc_id,
        "document_id": doc_id,
        "corpus_version": corpus_version,
        "question": title,
        "title": title,
        "content": content,
        "source": record.get("source"),
        "content_type": record.get("content_type"),
        "domain": "health_inbody",
        "language": record.get("language", "vi"),
    }
    return payloads, search_document


def build_chunk_vectors(
    record: dict[str, Any],
    line_number: int,
    chunk_size: int,
    chunk_overlap: int,
    embedding_batch_size: int,
    corpus_version: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split a document, generate embeddings, and build Qdrant vectors."""
    payloads, search_document = build_chunk_payloads(
        record,
        line_number=line_number,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        corpus_version=corpus_version,
    )
    vectors = embed_chunk_payloads(
        payloads,
        embedding_batch_size=embedding_batch_size,
    )
    return vectors, search_document


def embed_chunk_payloads(
    payloads: dict[str, dict[str, Any]],
    embedding_batch_size: int,
) -> dict[str, dict[str, Any]]:
    """Generate vectors only for the supplied canonical chunk payloads."""
    payload_items = list(payloads.items())
    vectors: dict[str, dict[str, Any]] = {}

    for batch_start in range(0, len(payload_items), embedding_batch_size):
        payload_batch = payload_items[
            batch_start : batch_start + embedding_batch_size
        ]
        batch_texts = [
            str(payload.get("content") or "")
            for _, payload in payload_batch
        ]
        batch_embeddings = get_embedding_safe(batch_texts)

        if not isinstance(batch_embeddings, list):
            raise RuntimeError("Embedding service returned a non-list response")
        if batch_embeddings and isinstance(batch_embeddings[0], (int, float)):
            batch_embeddings = [batch_embeddings]
        if len(batch_embeddings) != len(payload_batch):
            raise RuntimeError(
                "Embedding count mismatch: "
                f"expected {len(payload_batch)}, got {len(batch_embeddings)}"
            )

        for (point_id, payload), embedding in zip(
            payload_batch,
            batch_embeddings,
        ):
            vectors[point_id] = {
                "vector": embedding,
                "payload": payload,
            }

    return vectors


def import_embedding_dataset(
    data_file_path: str | Path = DEFAULT_DATA_FILE,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    batch_size: int = 50,
    embedding_batch_size: int = 32,
    limit: int | None = None,
    vector_size: int = DEFAULT_VECTOR_SIZE,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    skip_collection_create: bool = False,
    dry_run: bool = False,
    corpus_version: str = DEFAULT_CORPUS_VERSION,
    start_line: int = 1,
    manifest_file: str | Path | None = None,
    skip_existing_points: bool = False,
) -> dict[str, Any]:
    """
    Import corpus Health/InBody đã chuẩn hóa vào Qdrant.

    `dry_run=True` chỉ validate và đếm document/chunk, không gọi embedding/Qdrant.
    """
    data_path = Path(data_file_path)
    manifest_path = Path(manifest_file) if manifest_file else None
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    if start_line < 1:
        raise ValueError("start_line must be at least 1")
    if not dry_run and not corpus_version:
        raise ValueError(
            "corpus_version is required for a real import; set CORPUS_VERSION "
            "or pass --corpus-version"
        )

    logger.info("Import dataset: %s", data_path)
    logger.info("Collection: %s", collection_name)
    logger.info("Batch size: %s, limit: %s", batch_size, limit or "none")
    logger.info("Embedding request batch size: %s", embedding_batch_size)
    logger.info("Corpus version: %s", corpus_version or "dry-run-unversioned")
    logger.info("Starting from JSONL line: %s", start_line)
    logger.info("Skip existing Qdrant points: %s", skip_existing_points)

    if embedding_batch_size < 1 or embedding_batch_size > 32:
        raise ValueError("embedding_batch_size must be between 1 and 32")

    if not dry_run and not skip_collection_create:
        try:
            create_collection_safe(collection_name, vector_size=vector_size)
            logger.info("Created Qdrant collection: %s", collection_name)
        except Exception as exc:
            logger.info("Collection create skipped/failed, continuing: %s", exc)

    if not dry_run:
        ensure_payload_indexes_safe(collection_name)
        logger.info("Verified required payload indexes: %s", collection_name)

    existing_point_ids: set[str] = set()
    if not dry_run and skip_existing_points:
        existing_point_ids = get_collection_point_ids_safe(collection_name)
        logger.info(
            "Loaded %s existing point IDs; only missing chunks will be embedded",
            len(existing_point_ids),
        )

    vectors_batch: dict[str, dict[str, Any]] = {}
    counts_by_content_type: dict[str, int] = {}
    processed_docs = 0
    skipped_docs = 0
    error_count = 0
    total_chunks = 0
    validation_errors: list[str] = []
    fatal_error: str | None = None
    last_processed_line = start_line - 1
    last_successful_upsert_line = start_line - 1
    selected_records = 0
    upserted_chunks = 0
    newly_embedded_chunks = 0
    skipped_existing_chunks = 0
    initial_existing_points = len(existing_point_ids)
    data_file_sha256 = sha256_file(data_path)
    started_at = datetime.now(timezone.utc).isoformat()

    for line_number, record in load_jsonl(data_path):
        if line_number < start_line:
            continue
        if limit is not None and selected_records >= limit:
            break
        selected_records += 1
        last_processed_line = line_number

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

            if skip_existing_points:
                payloads, _ = build_chunk_payloads(
                    record,
                    line_number=line_number,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    corpus_version=corpus_version,
                )
                if not payloads:
                    skipped_docs += 1
                    logger.warning("line %s: no chunks created", line_number)
                    continue

                total_chunks += len(payloads)
                missing_payloads = {
                    point_id: payload
                    for point_id, payload in payloads.items()
                    if point_id not in existing_point_ids
                }
                skipped_existing_chunks += len(payloads) - len(missing_payloads)
                if not missing_payloads:
                    processed_docs += 1
                    continue

                vectors = embed_chunk_payloads(
                    missing_payloads,
                    embedding_batch_size=embedding_batch_size,
                )
                existing_point_ids.update(vectors)
            else:
                vectors, _ = build_chunk_vectors(
                    record,
                    line_number=line_number,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    embedding_batch_size=embedding_batch_size,
                    corpus_version=corpus_version,
                )
                total_chunks += len(vectors)

            if not vectors:
                skipped_docs += 1
                logger.warning("line %s: no chunks created", line_number)
                continue

            vectors_batch.update(vectors)
            processed_docs += 1
            newly_embedded_chunks += len(vectors)

            if len(vectors_batch) >= batch_size:
                add_vector_safe(collection_name=collection_name, vectors=vectors_batch, batch_size=batch_size)
                upserted_chunks += len(vectors_batch)
                last_successful_upsert_line = line_number
                logger.info(
                    "Upserted batch: %s chunks, processed_docs=%s",
                    len(vectors_batch),
                    processed_docs,
                )
                vectors_batch = {}
                write_import_manifest(
                    manifest_path,
                    {
                        "status": "running",
                        "collection_name": collection_name,
                        "corpus_version": corpus_version,
                        "data_file": str(data_path),
                        "data_file_sha256": data_file_sha256,
                        "started_at": started_at,
                        "last_processed_line": last_processed_line,
                        "last_successful_upsert_line": last_successful_upsert_line,
                        "processed_docs": processed_docs,
                        "total_chunks": total_chunks,
                        "initial_existing_points": initial_existing_points,
                        "skipped_existing_chunks": skipped_existing_chunks,
                        "newly_embedded_chunks": newly_embedded_chunks,
                        "upserted_chunks": upserted_chunks,
                        "error_count": error_count,
                    },
                )

        except ImportWriteError as exc:
            error_count += 1
            fatal_error = str(exc)
            logger.exception(
                "Fatal Qdrant write error near line %s; stopping import",
                line_number,
            )
            break
        except Exception as exc:
            skipped_docs += 1
            error_count += 1
            logger.exception("line %s: import failed: %s", line_number, exc)

    if vectors_batch and not dry_run and fatal_error is None:
        try:
            add_vector_safe(collection_name=collection_name, vectors=vectors_batch, batch_size=batch_size)
            upserted_chunks += len(vectors_batch)
            last_successful_upsert_line = last_processed_line
            logger.info("Upserted final batch: %s chunks", len(vectors_batch))
        except ImportWriteError as exc:
            error_count += 1
            fatal_error = str(exc)
            logger.exception("Fatal Qdrant write error in final batch")

    if not dry_run and fatal_error is None:
        logger.warning(
            "BM25 was not initialized by the importer because the current BM25 "
            "index is process-local and would disappear when this CLI exits"
        )

    result = {
        "status": error_count == 0 and fatal_error is None,
        "dry_run": dry_run,
        "data_file": str(data_path),
        "data_file_sha256": data_file_sha256,
        "collection_name": collection_name,
        "corpus_version": corpus_version or None,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "start_line": start_line,
        "last_processed_line": last_processed_line,
        "last_successful_upsert_line": last_successful_upsert_line,
        "processed_docs": processed_docs,
        "skipped_docs": skipped_docs,
        "total_chunks": total_chunks,
        "skip_existing_points": skip_existing_points,
        "initial_existing_points": initial_existing_points,
        "skipped_existing_chunks": skipped_existing_chunks,
        "newly_embedded_chunks": newly_embedded_chunks,
        "upserted_chunks": upserted_chunks,
        "bm25_index_persisted": False,
        "counts_by_content_type": counts_by_content_type,
        "error_count": error_count,
        "validation_errors_preview": validation_errors[:20],
        "fatal_error": fatal_error,
    }
    write_import_manifest(manifest_path, result)
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
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=32,
        help="Number of chunk texts sent to the embedding API per request (1-32).",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--vector-size", type=int, default=DEFAULT_VECTOR_SIZE)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--skip-collection-create", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--corpus-version",
        default=DEFAULT_CORPUS_VERSION,
        help="Immutable corpus version stored in every payload.",
    )
    parser.add_argument(
        "--start-line",
        type=int,
        default=1,
        help="Resume from this 1-based JSONL line; point IDs are idempotent.",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=None,
        help="Write an atomic JSON progress/final manifest.",
    )
    parser.add_argument(
        "--skip-existing-points",
        action="store_true",
        help=(
            "Scan target point IDs once and embed only missing stable IDs. "
            "Use for safe resume or after verified vector reuse."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_embedding_dataset(
        data_file_path=args.data_file,
        collection_name=args.collection,
        batch_size=args.batch_size,
        embedding_batch_size=args.embedding_batch_size,
        limit=args.limit,
        vector_size=args.vector_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        skip_collection_create=args.skip_collection_create,
        dry_run=args.dry_run,
        corpus_version=args.corpus_version,
        start_line=args.start_line,
        manifest_file=args.manifest_file,
        skip_existing_points=args.skip_existing_points,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] else 1)


if __name__ == "__main__":
    main()

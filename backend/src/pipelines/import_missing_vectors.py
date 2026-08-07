"""Resume a Qdrant import by embedding missing chunks across document boundaries.

This command is intentionally separate from the legacy document-at-a-time
importer.  It keeps the stable-ID/checkpoint guarantees while filling the
embedding request batch from multiple documents, which avoids many tiny model
calls for short chunks.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import DEFAULT_COLLECTION_NAME, DEFAULT_CORPUS_VERSION
from pipelines.import_data import (
    DEFAULT_DATA_FILE,
    ImportWriteError,
    add_vector_safe,
    build_chunk_payloads,
    embed_chunk_payloads,
    ensure_payload_indexes_safe,
    get_collection_point_ids_safe,
    load_jsonl,
    sha256_file,
    validate_document,
    write_import_manifest,
)
from core.utils import setup_logging
from rag.qdrant.client import get_collection_stats

logger = logging.getLogger(__name__)


def import_missing_vectors(
    data_file: str | Path = DEFAULT_DATA_FILE,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    corpus_version: str = DEFAULT_CORPUS_VERSION,
    start_line: int = 1,
    qdrant_batch_size: int = 100,
    embedding_batch_size: int = 32,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    manifest_file: str | Path | None = None,
) -> dict[str, Any]:
    """Embed only missing stable IDs and checkpoint after each model batch."""
    data_path = Path(data_file)
    manifest_path = Path(manifest_file) if manifest_file else None
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    if start_line < 1:
        raise ValueError("start_line must be at least 1")
    if qdrant_batch_size < 1:
        raise ValueError("qdrant_batch_size must be at least 1")
    if embedding_batch_size < 1 or embedding_batch_size > 32:
        raise ValueError("embedding_batch_size must be between 1 and 32")

    ensure_payload_indexes_safe(collection_name)
    stats_before = get_collection_stats(collection_name)
    if stats_before.get("error"):
        raise RuntimeError(str(stats_before["error"]))
    existing_point_ids = get_collection_point_ids_safe(collection_name)
    started_at = datetime.now(timezone.utc).isoformat()
    checksum = sha256_file(data_path)

    pending_payloads: dict[str, dict[str, Any]] = {}
    processed_docs = 0
    skipped_docs = 0
    error_count = 0
    validation_errors: list[str] = []
    total_chunks = 0
    skipped_existing_chunks = 0
    newly_embedded_chunks = 0
    upserted_chunks = 0
    last_processed_line = start_line - 1
    last_successful_upsert_line = start_line - 1
    fatal_error: str | None = None
    counts_by_content_type: dict[str, int] = {}

    def flush_pending(flush_line: int) -> None:
        nonlocal pending_payloads
        nonlocal newly_embedded_chunks, upserted_chunks
        nonlocal last_successful_upsert_line, fatal_error
        if not pending_payloads:
            return
        payloads = pending_payloads
        pending_payloads = {}
        vectors = embed_chunk_payloads(
            payloads,
            embedding_batch_size=embedding_batch_size,
        )
        try:
            add_vector_safe(
                collection_name=collection_name,
                vectors=vectors,
                batch_size=qdrant_batch_size,
            )
        except ImportWriteError as exc:
            fatal_error = str(exc)
            raise
        existing_point_ids.update(vectors)
        newly_embedded_chunks += len(vectors)
        upserted_chunks += len(vectors)
        last_successful_upsert_line = flush_line
        write_import_manifest(
            manifest_path,
            {
                "status": "running",
                "collection_name": collection_name,
                "corpus_version": corpus_version,
                "data_file": str(data_path),
                "data_file_sha256": checksum,
                "started_at": started_at,
                "last_processed_line": last_processed_line,
                "last_successful_upsert_line": last_successful_upsert_line,
                "processed_docs": processed_docs,
                "total_chunks": total_chunks,
                "initial_existing_points": stats_before.get("points_count", 0),
                "skipped_existing_chunks": skipped_existing_chunks,
                "newly_embedded_chunks": newly_embedded_chunks,
                "upserted_chunks": upserted_chunks,
                "error_count": error_count,
            },
        )
        logger.info(
            "Upserted cross-document batch: %s vectors, line=%s, total_new=%s",
            len(vectors),
            flush_line,
            newly_embedded_chunks,
        )

    for line_number, record in load_jsonl(data_path):
        if line_number < start_line:
            continue
        last_processed_line = line_number
        errors = validate_document(record, line_number)
        if errors:
            skipped_docs += 1
            error_count += len(errors)
            validation_errors.extend(errors[:5])
            continue

        content_type = str(record["content_type"])
        counts_by_content_type[content_type] = counts_by_content_type.get(content_type, 0) + 1
        payloads, _ = build_chunk_payloads(
            record,
            line_number=line_number,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            corpus_version=corpus_version,
        )
        processed_docs += 1
        total_chunks += len(payloads)
        missing_payloads = {
            point_id: payload
            for point_id, payload in payloads.items()
            if point_id not in existing_point_ids
        }
        skipped_existing_chunks += len(payloads) - len(missing_payloads)
        pending_payloads.update(missing_payloads)
        if len(pending_payloads) >= embedding_batch_size:
            try:
                flush_pending(line_number)
            except ImportWriteError:
                break

    if fatal_error is None:
        try:
            flush_pending(last_processed_line)
        except ImportWriteError:
            pass

    stats_after = get_collection_stats(collection_name)
    result = {
        "status": error_count == 0 and fatal_error is None,
        "data_file": str(data_path),
        "data_file_sha256": checksum,
        "collection_name": collection_name,
        "corpus_version": corpus_version,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "start_line": start_line,
        "last_processed_line": last_processed_line,
        "last_successful_upsert_line": last_successful_upsert_line,
        "processed_docs": processed_docs,
        "skipped_docs": skipped_docs,
        "total_chunks": total_chunks,
        "initial_existing_points": stats_before.get("points_count", 0),
        "skipped_existing_chunks": skipped_existing_chunks,
        "newly_embedded_chunks": newly_embedded_chunks,
        "upserted_chunks": upserted_chunks,
        "target_points_after": stats_after.get("points_count"),
        "counts_by_content_type": counts_by_content_type,
        "error_count": error_count,
        "validation_errors_preview": validation_errors[:20],
        "fatal_error": fatal_error,
    }
    write_import_manifest(manifest_path, result)
    logger.info("Missing-only import result: %s", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--corpus-version", default=DEFAULT_CORPUS_VERSION)
    parser.add_argument("--start-line", type=int, default=1)
    parser.add_argument("--qdrant-batch-size", type=int, default=100)
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--manifest-file", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    result = import_missing_vectors(
        data_file=args.data_file,
        collection_name=args.collection,
        corpus_version=args.corpus_version,
        start_line=args.start_line,
        qdrant_batch_size=args.qdrant_batch_size,
        embedding_batch_size=args.embedding_batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        manifest_file=args.manifest_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] else 1)


if __name__ == "__main__":
    main()

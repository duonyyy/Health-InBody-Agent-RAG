"""Reuse verified vectors from an older Qdrant collection.

The command rebuilds canonical payloads from the current JSONL corpus, verifies
that every source point has the same stable ID and chunk text, and only then
copies vectors into a versioned target collection. It never deletes points or
changes aliases.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from collection_naming import validate_collection_name
from configs import DEFAULT_CORPUS_VERSION, DEFAULT_VECTOR_SIZE
from import_data import (
    DEFAULT_DATA_FILE,
    build_chunk_payloads,
    load_jsonl,
    sha256_file,
    validate_document,
    write_import_manifest,
)
from vectorize import (
    add_vector,
    client,
    ensure_payload_indexes,
    get_collection_stats,
)

logger = logging.getLogger(__name__)


def _scroll_points(
    collection_name: str,
    *,
    with_vectors: bool,
    batch_size: int = 256,
) -> Iterator[Any]:
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=with_vectors,
        )
        yield from points
        if offset is None:
            break


def _build_expected_payloads(
    data_path: Path,
    *,
    corpus_version: str,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    for line_number, record in load_jsonl(data_path):
        errors = validate_document(record, line_number)
        if errors:
            raise ValueError("; ".join(errors))
        payloads, _ = build_chunk_payloads(
            record,
            line_number=line_number,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            corpus_version=corpus_version,
        )
        duplicate_ids = expected.keys() & payloads.keys()
        if duplicate_ids:
            preview = sorted(duplicate_ids)[:5]
            raise ValueError(f"Duplicate stable point IDs in corpus: {preview}")
        expected.update(payloads)
    return expected


def reuse_vectors(
    *,
    source_collection: str,
    target_collection: str,
    data_file: str | Path,
    corpus_version: str,
    expected_reusable_points: int,
    expected_target_points_before: int,
    batch_size: int = 50,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    manifest_file: str | Path | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    """Validate and optionally copy reusable vectors with corrected payloads."""
    if source_collection == target_collection:
        raise ValueError("Source and target collections must differ")
    if not corpus_version:
        raise ValueError("corpus_version is required")
    if expected_reusable_points < 1:
        raise ValueError("expected_reusable_points must be at least 1")
    if expected_target_points_before < 0:
        raise ValueError("expected_target_points_before cannot be negative")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    data_path = Path(data_file)
    manifest_path = Path(manifest_file) if manifest_file else None
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    logging.getLogger("splitter").setLevel(logging.WARNING)
    started_at = datetime.now(timezone.utc).isoformat()
    data_checksum = sha256_file(data_path)
    expected = _build_expected_payloads(
        data_path,
        corpus_version=corpus_version,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    source_stats = get_collection_stats(source_collection)
    target_stats = get_collection_stats(target_collection)
    if "error" in source_stats:
        raise RuntimeError(source_stats["error"])
    if "error" in target_stats:
        raise RuntimeError(target_stats["error"])
    if source_stats["vector_size"] != DEFAULT_VECTOR_SIZE:
        raise ValueError(
            f"Source vector size is {source_stats['vector_size']}, "
            f"expected {DEFAULT_VECTOR_SIZE}"
        )
    if target_stats["vector_size"] != source_stats["vector_size"]:
        raise ValueError(
            "Source/target vector sizes differ: "
            f"{source_stats['vector_size']} != {target_stats['vector_size']}"
        )
    if int(source_stats["points_count"] or 0) != expected_reusable_points:
        raise ValueError(
            f"Source has {source_stats['points_count']} points, "
            f"expected {expected_reusable_points}"
        )
    if int(target_stats["points_count"] or 0) != expected_target_points_before:
        raise ValueError(
            f"Target has {target_stats['points_count']} points before copy, "
            f"expected {expected_target_points_before}"
        )

    id_matches = 0
    content_matches = 0
    content_mismatches = 0
    unexpected_ids = 0
    for point in _scroll_points(source_collection, with_vectors=False):
        point_id = str(point.id)
        expected_payload = expected.get(point_id)
        if expected_payload is None:
            unexpected_ids += 1
            continue
        id_matches += 1
        source_content = str((point.payload or {}).get("content") or "")
        if source_content == expected_payload["content"]:
            content_matches += 1
        else:
            content_mismatches += 1

    validation = {
        "expected_corpus_chunks": len(expected),
        "source_points": source_stats["points_count"],
        "id_matches": id_matches,
        "content_matches": content_matches,
        "content_mismatches": content_mismatches,
        "unexpected_ids": unexpected_ids,
        "remaining_to_embed": len(expected) - content_matches,
    }
    if (
        content_matches != expected_reusable_points
        or content_mismatches
        or unexpected_ids
    ):
        raise ValueError(f"Source vector validation failed: {validation}")

    copied_points = 0
    if execute:
        ensure_payload_indexes(target_collection, raise_on_error=True)
        vectors_batch: dict[str, dict[str, Any]] = {}
        for point in _scroll_points(source_collection, with_vectors=True):
            point_id = str(point.id)
            expected_payload = expected[point_id]
            if not isinstance(point.vector, list) or not point.vector:
                raise ValueError(f"Point {point_id} has no reusable dense vector")
            vectors_batch[point_id] = {
                "vector": point.vector,
                "payload": expected_payload,
            }
            if len(vectors_batch) >= batch_size:
                add_vector(
                    target_collection,
                    vectors=vectors_batch,
                    batch_size=batch_size,
                    raise_on_error=True,
                )
                copied_points += len(vectors_batch)
                vectors_batch = {}
                write_import_manifest(
                    manifest_path,
                    {
                        "status": "running",
                        "source_collection": source_collection,
                        "target_collection": target_collection,
                        "corpus_version": corpus_version,
                        "data_file_sha256": data_checksum,
                        "copied_points": copied_points,
                        **validation,
                    },
                )
        if vectors_batch:
            add_vector(
                target_collection,
                vectors=vectors_batch,
                batch_size=batch_size,
                raise_on_error=True,
            )
            copied_points += len(vectors_batch)

    final_target_stats = get_collection_stats(target_collection)
    if execute and int(final_target_stats.get("points_count") or 0) != content_matches:
        raise RuntimeError(
            f"Target verification failed: expected {content_matches} points, "
            f"found {final_target_stats.get('points_count')}"
        )

    result = {
        "status": True,
        "dry_run": not execute,
        "source_collection": source_collection,
        "target_collection": target_collection,
        "corpus_version": corpus_version,
        "data_file": str(data_path),
        "data_file_sha256": data_checksum,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "target_points_before": target_stats["points_count"],
        "target_points_after": final_target_stats.get("points_count"),
        "copied_points": copied_points,
        **validation,
    }
    write_import_manifest(manifest_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely reuse verified vectors in a versioned collection"
    )
    parser.add_argument(
        "--source-collection",
        required=True,
        type=validate_collection_name,
    )
    parser.add_argument(
        "--target-collection",
        required=True,
        type=validate_collection_name,
    )
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument(
        "--corpus-version",
        default=DEFAULT_CORPUS_VERSION,
    )
    parser.add_argument("--expected-reusable-points", type=int, required=True)
    parser.add_argument(
        "--expected-target-points-before",
        type=int,
        required=True,
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--manifest-file", type=Path, default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write to the target collection after full validation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = reuse_vectors(
        source_collection=args.source_collection,
        target_collection=args.target_collection,
        data_file=args.data_file,
        corpus_version=args.corpus_version,
        expected_reusable_points=args.expected_reusable_points,
        expected_target_points_before=args.expected_target_points_before,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        manifest_file=args.manifest_file,
        execute=args.execute,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

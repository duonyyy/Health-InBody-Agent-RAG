"""Import Health/InBody embedding dataset into a physical staging Qdrant collection.

Script này dùng corpus đã chuẩn hóa từ `data_pipeline`, mặc định là:

`data_pipeline/dataset/processed/embedding_documents.jsonl`

Mọi lượt import thật đều bắt buộc qua staging admission (chặn serving alias và
physical target đang phục vụ, fail-closed khi không xác minh được topology), giữ
write lease chống trùng lắp với activation, xác thực vector trước upsert, và ghi
checkpoint/manifest nguyên tử phản ánh trung thực kết quả commit từng batch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from core.config import (
    DEFAULT_COLLECTION_ALIAS,
    DEFAULT_CORPUS_VERSION,
    DEFAULT_VECTOR_SIZE,
)
from core.utils import setup_logging
from rag.corpus_lifecycle import (
    CorpusConflictError,
    CorpusLeaseManager,
    QdrantWriteError,
    atomic_write_json,
    build_release_manifest,
    build_resume_signature,
    check_existing_point_conflict,
    compute_chunk_set_fingerprint,
    current_embedding_config,
    finalize_write_receipt,
    make_release_id,
    new_write_receipt,
    record_skip,
    save_release_manifest,
    validate_embeddings_alignment,
    verify_resume_compatibility,
    verify_staging_write_target,
)
from rag.corpus_policy import validate_shared_document
from rag.provenance import (
    ALLOWED_SOURCE_TIERS,
    is_verified_medical_review,
    load_review_registry,
    resolve_document_provenance,
)

try:
    from rag.splitter import split_document as project_split_document
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
TRUSTED_SOURCE_FIELDS = {
    "source_url",
    "publisher",
    "source_tier",
    "published_at",
    "reviewed_at",
    "medical_review_status",
}
APPROVED_MEDICAL_REVIEW_STATUSES = {"approved"}


class SimpleDocument:
    """Fallback Document tối giản khi môi trường local chưa cài LangChain."""

    def __init__(self, page_content: str, metadata: dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata


class ImportWriteError(QdrantWriteError):
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


def _get_default_qdrant_client() -> Any:
    from rag.qdrant.client import client

    return client


def get_embedding_safe(
    text: str | list[str],
) -> list[float] | list[list[float]]:
    """Lazy import embedding để dry-run không cần đủ backend dependencies."""
    from llm.client import get_embedding

    return get_embedding(text)


def add_vector_safe(
    collection_name: str,
    vectors: dict[str, Any],
    batch_size: int,
    *,
    expected_vector_size: Optional[int] = None,
    corpus_version: Optional[str] = None,
    release_id: Optional[str] = None,
    embedding_fingerprint: Optional[str] = None,
    lease: Any = None,
    lease_manager: Any = None,
    qdrant_client: Any = None,
) -> dict[str, Any]:
    """Lazy import Qdrant writer returning honest WriteReceipt or raising ImportWriteError."""
    from rag.qdrant.client import add_vector

    try:
        receipt = add_vector(
            collection_name=collection_name,
            vectors=vectors,
            batch_size=batch_size,
            raise_on_error=True,
            expected_vector_size=expected_vector_size,
            corpus_version=corpus_version,
            release_id=release_id,
            embedding_fingerprint=embedding_fingerprint,
            enforce_staging_policy=True,
            require_corpus_version=bool(corpus_version),
            lease=lease,
            lease_manager=lease_manager,
            qdrant_client=qdrant_client,
        )
        return receipt
    except QdrantWriteError as exc:
        raise ImportWriteError(str(exc), receipt=exc.receipt) from exc
    except Exception as exc:
        raise ImportWriteError(
            f"Qdrant write failed for {len(vectors)} vector(s): {exc}"
        ) from exc


def create_collection_safe(
    collection_name: str,
    vector_size: int,
    *,
    qdrant_client: Any = None,
):
    """Lazy import Qdrant collection creator (guarded by staging admission)."""
    from rag.qdrant.client import create_collection

    return create_collection(
        collection_name,
        vector_size=vector_size,
        qdrant_client=qdrant_client,
        enforce_staging_policy=True,
    )


def ensure_payload_indexes_safe(collection_name: str, *, qdrant_client: Any = None):
    """Lazy import Qdrant payload-index setup."""
    from rag.qdrant.client import ensure_payload_indexes

    return ensure_payload_indexes(
        collection_name,
        raise_on_error=True,
        qdrant_client=qdrant_client,
    )


def get_collection_point_ids_safe(collection_name: str, *, qdrant_client: Any = None) -> set[str]:
    """Lazy import point-ID scan (prefer get_collection_point_fingerprints_safe for resume)."""
    from rag.qdrant.client import get_collection_point_ids

    return get_collection_point_ids(collection_name, qdrant_client=qdrant_client)


def get_collection_point_fingerprints_safe(
    collection_name: str,
    *,
    qdrant_client: Any = None,
) -> dict[str, dict[str, Any]]:
    """Lazy import content-hash/version fingerprint scan for safe content-verified resume."""
    from rag.qdrant.client import get_collection_point_fingerprints

    return get_collection_point_fingerprints(collection_name, qdrant_client=qdrant_client)


def initialize_search_index_safe(documents: list[dict[str, Any]]):
    """Lazy import BM25 search indexer."""
    from rag.search import initialize_search_index

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
    """Atomically persist import progress/result (fsync + replace) when a path is configured."""
    if path is None:
        return
    atomic_write_json(path, payload)


def _source_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(record.get("metadata") or {})
    return {
        field: record.get(field) or metadata.get(field)
        for field in TRUSTED_SOURCE_FIELDS
    }


def validate_document(
    record: dict[str, Any],
    line_number: int,
    require_trusted_source_metadata: bool = False,
    *,
    review_registry: Mapping[str, Any] | None = None,
    allow_synthetic_registry: bool = False,
) -> list[str]:
    """Kiểm tra document có đúng schema embedding của dự án không."""
    errors: list[str] = []
    try:
        validate_shared_document(record)
    except ValueError as exc:
        errors.append(f"line {line_number}: {exc}")
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

    if require_trusted_source_metadata:
        provenance = resolve_document_provenance(
            record,
            content=content,
            registry=review_registry,
            is_seed=str(record.get("source") or "") == "internal_seed",
            allow_synthetic_registry=allow_synthetic_registry,
        )
        effective_fields = {
            "source_url": provenance.get("source_url"),
            "publisher": provenance.get("publisher"),
            "source_tier": provenance.get("source_tier"),
            "published_at": provenance.get("published_at"),
            "reviewed_at": provenance.get("reviewed_at"),
            "medical_review_status": (
                provenance.get("medical_review_status")
                if provenance.get("review_verification_status") == "verified"
                else None
            ),
        }
        missing_source_fields = sorted(
            field for field, value in effective_fields.items() if not str(value or "").strip()
        )
        if missing_source_fields:
            errors.append(
                f"line {line_number}: missing trusted source metadata: "
                + ", ".join(missing_source_fields)
            )

        raw_url = str(_source_metadata(record).get("source_url") or "").strip()
        if raw_url and not provenance.get("source_url"):
            errors.append(f"line {line_number}: source_url must be an absolute HTTP(S) URL")

        source_tier = str(provenance.get("source_tier") or "").strip()
        if source_tier and (
            source_tier not in ALLOWED_SOURCE_TIERS or not provenance.get("source_tier_verified")
        ):
            errors.append(f"line {line_number}: untrusted source_tier={source_tier}")

        verification_status = provenance.get("review_verification_status")
        if verification_status == "stale_content_mismatch":
            errors.append(
                f"line {line_number}: medical review is stale (content_hash mismatch)"
            )
        elif verification_status == "unverified_legacy":
            errors.append(
                f"line {line_number}: claimed medical_review_status is not backed by a managed review registry record"
            )
        elif not is_verified_medical_review(provenance):
            errors.append(
                f"line {line_number}: medical_review_status is not verified/approved in review registry"
            )

        for field in ("published_at", "reviewed_at"):
            value = str(effective_fields.get(field) or "").strip()
            if value:
                try:
                    date.fromisoformat(value[:10])
                except ValueError:
                    errors.append(f"line {line_number}: {field} must start with ISO date YYYY-MM-DD")

    return errors


def build_chunk_payloads(
    record: dict[str, Any],
    line_number: int,
    chunk_size: int,
    chunk_overlap: int,
    corpus_version: str,
    *,
    review_registry: Mapping[str, Any] | None = None,
    allow_synthetic_registry: bool = False,
    embedding_fingerprint: Optional[str] = None,
    release_id: Optional[str] = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split one document and build stable point IDs plus canonical payloads."""
    doc_id = str(record["doc_id"])
    document_id = str(record.get("document_id") or doc_id)
    title = str(record.get("title") or "")
    content = str(record.get("content") or "")
    provenance = resolve_document_provenance(
        record,
        content=content,
        registry=review_registry,
        is_seed=str(record.get("source") or "") == "internal_seed",
        allow_synthetic_registry=allow_synthetic_registry,
    )
    raw_metadata = dict(record.get("metadata") or {})
    raw_metadata.pop("review_status", None)
    metadata = {
        **raw_metadata,
        **provenance,
        "doc_id": doc_id,
        "document_id": document_id,
        "corpus_version": corpus_version,
        "title": title,
        "source": record.get("source"),
        "content_type": record.get("content_type"),
        "domain": "health_inbody",
        "language": record.get("language", "vi"),
        "line_number": line_number,
    }
    if embedding_fingerprint:
        metadata["embedding_fingerprint"] = embedding_fingerprint
    if release_id:
        metadata["release_id"] = release_id

    chunks = split_document_safe(
        content,
        metadata=metadata,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    payloads: dict[str, dict[str, Any]] = {}
    for chunk_index, chunk in enumerate(chunks, start=1):
        chunk_id = f"{document_id}-{chunk_index}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
        content_hash = hashlib.sha256(
            chunk.page_content.encode("utf-8")
        ).hexdigest()
        payloads[point_id] = {
            **chunk.metadata,
            "doc_id": doc_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "question": title,
            "content": chunk.page_content,
            "text": chunk.page_content,
            "content_hash": content_hash,
            "qdrant_point_id": point_id,
        }

    search_document = {
        **provenance,
        "doc_id": doc_id,
        "document_id": document_id,
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
    *,
    vector_size: Optional[int] = None,
    review_registry: Mapping[str, Any] | None = None,
    allow_synthetic_registry: bool = False,
    embedding_fingerprint: Optional[str] = None,
    release_id: Optional[str] = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split a document, generate embeddings, and build validated Qdrant vectors."""
    payloads, search_document = build_chunk_payloads(
        record,
        line_number=line_number,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        corpus_version=corpus_version,
        review_registry=review_registry,
        allow_synthetic_registry=allow_synthetic_registry,
        embedding_fingerprint=embedding_fingerprint,
        release_id=release_id,
    )
    vectors = embed_chunk_payloads(
        payloads,
        embedding_batch_size=embedding_batch_size,
        expected_vector_size=vector_size,
    )
    return vectors, search_document


def embed_chunk_payloads(
    payloads: dict[str, dict[str, Any]],
    embedding_batch_size: int,
    *,
    expected_vector_size: Optional[int] = None,
) -> dict[str, dict[str, Any]]:
    """Generate and validate vectors only for the supplied canonical chunk payloads."""
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

        validated_embeddings = validate_embeddings_alignment(
            payload_batch,
            batch_embeddings,
            expected_vector_size=expected_vector_size,
        )

        for (point_id, payload), embedding in zip(
            payload_batch,
            validated_embeddings,
        ):
            vectors[point_id] = {
                "vector": embedding,
                "payload": payload,
            }

    return vectors


def import_embedding_dataset(
    data_file_path: str | Path = DEFAULT_DATA_FILE,
    collection_name: str | None = None,
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
    release_manifest_file: str | Path | None = None,
    skip_existing_points: bool = False,
    require_trusted_source_metadata: bool = False,
    review_registry_path: str | Path | None = None,
    review_registry: Mapping[str, Any] | None = None,
    allow_synthetic_registry: bool = False,
    qdrant_client: Any = None,
    lock_dir: str | Path | None = None,
    release_id: str | None = None,
    embedding_model_id: str | None = None,
) -> dict[str, Any]:
    """
    Import corpus Health/InBody đã chuẩn hóa vào physical staging collection trong Qdrant.

    - Không bao giờ mặc định ghi vào serving alias.
    - Fail-closed nếu không xác minh được Qdrant alias topology (trừ dry-run offline).
    - Giữ write lease chống trùng lắp với activation.
    - Resume kiểm cả content_hash, corpus_version và embedding_fingerprint; báo conflict nếu khác.
    - Checkpoint chỉ tiến sau batch được Qdrant xác nhận commit.
    """
    data_path = Path(data_file_path)
    manifest_path = Path(manifest_file) if manifest_file else None
    release_manifest_path = Path(release_manifest_file) if release_manifest_file else None
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    if start_line < 1:
        raise ValueError("start_line must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if embedding_batch_size < 1 or embedding_batch_size > 32:
        raise ValueError("embedding_batch_size must be between 1 and 32")

    # A line checkpoint cannot prove every earlier input was committed: validation
    # errors and multiple chunks can leave gaps. Rescan and verify each point.
    if not dry_run and start_line > 1:
        raise CorpusConflictError(
            "Resume theo start_line chưa chứng minh được các dòng trước đã commit; "
            "hãy quét lại từ dòng 1 với skip_existing_points hoặc tạo staging release mới"
        )

    active_qdrant = None
    if not dry_run:
        active_qdrant = _get_default_qdrant_client() if qdrant_client is None else qdrant_client

    # R06: Single staging admission gate BEFORE any collection create, embed, or upsert.
    effective_target = collection_name
    if dry_run and not effective_target:
        # Offline dry-run requires an explicit non-serving label for auditability.
        effective_target = "dry_run_unassigned_staging"
    admission = verify_staging_write_target(
        effective_target,
        qdrant_client=active_qdrant,
        corpus_version=corpus_version,
        require_corpus_version=not dry_run,
        require_allowlist=False,
        dry_run=dry_run,
    )
    resolved_collection = admission["target_collection"]
    resolved_version = admission["corpus_version"] or ""

    emb_cfg = current_embedding_config(
        vector_size=vector_size,
        model_identifier=embedding_model_id,
    )
    embedding_fingerprint = emb_cfg["fingerprint"]
    data_file_sha256 = sha256_file(data_path)
    splitter_version = "langchain_splitter" if project_split_document is not None else "fallback_char_splitter"
    resume_signature = build_resume_signature(
        collection_name=resolved_collection,
        corpus_version=resolved_version or "dry-run",
        data_file_sha256=data_file_sha256,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        vector_size=vector_size,
        embedding_fingerprint=embedding_fingerprint,
        splitter_version=splitter_version,
    )

    # Check resume compatibility if resuming against an existing manifest/checkpoint.
    if manifest_path is not None and manifest_path.exists() and (start_line > 1 or skip_existing_points):
        prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verify_resume_compatibility(prior_manifest, resume_signature)

    resolved_release_id = release_id or make_release_id(resolved_version or "dry-run", data_file_sha256)

    logger.info("Import dataset: %s", data_path)
    logger.info("Target staging collection: %s", resolved_collection)
    logger.info("Batch size: %s, limit: %s", batch_size, limit or "none")
    logger.info("Embedding request batch size: %s", embedding_batch_size)
    logger.info("Corpus version: %s", resolved_version or "dry-run-unversioned")
    logger.info("Starting from JSONL line: %s", start_line)
    logger.info("Skip existing Qdrant points: %s", skip_existing_points)
    logger.info("Require trusted source metadata: %s", require_trusted_source_metadata)

    lease_manager: Optional[CorpusLeaseManager] = None
    lease = None
    if not dry_run:
        lease_manager = CorpusLeaseManager(lock_dir=lock_dir)
        lease = lease_manager.acquire_write_lease(
            resolved_collection,
            qdrant_client=active_qdrant,
            corpus_version=resolved_version,
            release_id=resolved_release_id,
            require_corpus_version=True,
        )

    receipt = new_write_receipt(
        collection_name=resolved_collection,
        corpus_version=resolved_version or None,
        release_id=resolved_release_id,
        dry_run=dry_run,
    )

    vectors_batch: dict[str, dict[str, Any]] = {}
    counts_by_content_type: dict[str, int] = {}
    all_chunk_identities: list[dict[str, Any]] = []
    provenance_counts = {
        "verified": 0,
        "provisional": 0,
        "unverified_legacy": 0,
        "stale_review": 0,
    }
    processed_docs = 0
    skipped_docs = 0
    error_count = 0
    total_chunks = 0
    validation_errors: list[str] = []
    conflicts: list[str] = []
    fatal_error: str | None = None
    last_processed_line = start_line - 1
    last_successful_upsert_line = start_line - 1
    committed_point_ids: list[str] = []
    selected_records = 0
    upserted_chunks = 0
    newly_embedded_chunks = 0
    skipped_existing_chunks = 0
    initial_existing_points = 0
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        if not dry_run and not skip_collection_create:
            try:
                create_collection_safe(
                    resolved_collection,
                    vector_size=vector_size,
                    qdrant_client=active_qdrant,
                )
                logger.info("Created Qdrant staging collection: %s", resolved_collection)
            except Exception as exc:
                # Re-raise admission/lock errors immediately; only ignore already-exists.
                from rag.corpus_lifecycle import (
                    CorpusAdmissionError,
                    CorpusLockError,
                    CorpusTopologyUnavailableError,
                )

                if isinstance(exc, (CorpusAdmissionError, CorpusLockError, CorpusTopologyUnavailableError)):
                    raise
                logger.info("Collection create skipped/existing, continuing: %s", exc)

        if not dry_run:
            ensure_payload_indexes_safe(resolved_collection, qdrant_client=active_qdrant)
            logger.info("Verified required payload indexes: %s", resolved_collection)

        existing_fingerprints: dict[str, dict[str, Any]] = {}
        if not dry_run and skip_existing_points:
            existing_fingerprints = get_collection_point_fingerprints_safe(
                resolved_collection,
                qdrant_client=active_qdrant,
            )
            initial_existing_points = len(existing_fingerprints)
            logger.info(
                "Loaded %s existing point fingerprints for content-verified resume",
                initial_existing_points,
            )

        active_review_registry = (
            review_registry
            if review_registry is not None
            else load_review_registry(
                review_registry_path,
                allow_synthetic=allow_synthetic_registry,
            )
        )

        def _merge_batch_receipt(batch_receipt: Mapping[str, Any]) -> None:
            receipt["attempted_points"] += int(batch_receipt.get("attempted_points") or 0)
            receipt["acknowledged_points"] += int(batch_receipt.get("acknowledged_points") or 0)
            receipt["committed_points"] += int(batch_receipt.get("committed_points") or 0)
            receipt["failed_points"] += int(batch_receipt.get("failed_points") or 0)
            receipt["unconfirmed_points"] += int(batch_receipt.get("unconfirmed_points") or 0)
            receipt["batches_attempted"] += int(batch_receipt.get("batches_attempted") or 0)
            receipt["batches_committed"] += int(batch_receipt.get("batches_committed") or 0)
            receipt["batches_unconfirmed"] += int(batch_receipt.get("batches_unconfirmed") or 0)
            receipt["batches_failed"] += int(batch_receipt.get("batches_failed") or 0)
            receipt["errors"].extend(batch_receipt.get("errors") or [])
            receipt["batch_receipts"].extend(batch_receipt.get("batch_receipts") or [])

        def _flush_batch(flush_line: int) -> None:
            nonlocal vectors_batch, upserted_chunks, last_successful_upsert_line
            if not vectors_batch:
                return
            batch_to_send = vectors_batch
            vectors_batch = {}
            batch_ids = list(batch_to_send.keys())
            try:
                batch_receipt = add_vector_safe(
                    collection_name=resolved_collection,
                    vectors=batch_to_send,
                    batch_size=batch_size,
                    expected_vector_size=vector_size,
                    corpus_version=resolved_version,
                    release_id=resolved_release_id,
                    embedding_fingerprint=embedding_fingerprint,
                    lease=lease,
                    lease_manager=lease_manager,
                    qdrant_client=active_qdrant,
                )
            except ImportWriteError as exc:
                if exc.receipt:
                    _merge_batch_receipt(exc.receipt)
                    upserted_chunks += int(exc.receipt.get("committed_points") or 0)
                else:
                    receipt["attempted_points"] += len(batch_to_send)
                    receipt["failed_points"] += len(batch_to_send)
                    receipt["batches_attempted"] += 1
                    receipt["batches_failed"] += 1
                    receipt["errors"].append({"line": flush_line, "error": str(exc)})
                raise

            _merge_batch_receipt(batch_receipt)
            committed_here = int(
                batch_receipt.get("committed_points")
                or batch_receipt.get("acknowledged_points")
                or 0
            )
            upserted_chunks += committed_here
            if batch_receipt.get("ok"):
                committed_point_ids.extend(batch_ids)
                for pid, item in batch_to_send.items():
                    payload = item["payload"]
                    existing_fingerprints[pid] = {
                        "qdrant_point_id": pid,
                        "document_id": payload.get("document_id"),
                        "chunk_id": payload.get("chunk_id"),
                        "content_hash": payload.get("content_hash"),
                        "corpus_version": payload.get("corpus_version"),
                        "embedding_fingerprint": payload.get("embedding_fingerprint"),
                    }
                last_successful_upsert_line = flush_line
                logger.info(
                    "Committed batch: %s chunks, processed_docs=%s, last_committed_line=%s",
                    committed_here,
                    processed_docs,
                    last_successful_upsert_line,
                )
                write_import_manifest(
                    manifest_path,
                    {
                        "status": "running",
                        "release_id": resolved_release_id,
                        "collection_name": resolved_collection,
                        "corpus_version": resolved_version,
                        "data_file": str(data_path),
                        "data_file_sha256": data_file_sha256,
                        "resume_signature": resume_signature,
                        "embedding_config": emb_cfg,
                        "started_at": started_at,
                        "last_processed_line": last_processed_line,
                        "last_successful_upsert_line": last_successful_upsert_line,
                        "committed_point_count": len(committed_point_ids),
                        "processed_docs": processed_docs,
                        "total_chunks": total_chunks,
                        "initial_existing_points": initial_existing_points,
                        "skipped_existing_chunks": skipped_existing_chunks,
                        "newly_embedded_chunks": newly_embedded_chunks,
                        "upserted_chunks": upserted_chunks,
                        "error_count": error_count,
                        "write_receipt": dict(receipt),
                    },
                )

        for line_number, record in load_jsonl(data_path):
            if line_number < start_line:
                continue
            if limit is not None and selected_records >= limit:
                break
            selected_records += 1
            last_processed_line = line_number

            errors = validate_document(
                record,
                line_number,
                require_trusted_source_metadata=require_trusted_source_metadata,
                review_registry=active_review_registry,
                allow_synthetic_registry=allow_synthetic_registry,
            )
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
                payloads, _ = build_chunk_payloads(
                    record,
                    line_number=line_number,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    corpus_version=resolved_version or "dry-run",
                    review_registry=active_review_registry,
                    allow_synthetic_registry=allow_synthetic_registry,
                    embedding_fingerprint=embedding_fingerprint,
                    release_id=resolved_release_id,
                )
                if not payloads:
                    skipped_docs += 1
                    logger.warning("line %s: no chunks created", line_number)
                    continue

                first_payload = next(iter(payloads.values()))
                rev_stat = str(first_payload.get("medical_review_status") or "provisional")
                if first_payload.get("review_verification_status") == "verified":
                    provenance_counts["verified"] += 1
                elif rev_stat == "unverified_legacy":
                    provenance_counts["unverified_legacy"] += 1
                elif rev_stat == "stale_review":
                    provenance_counts["stale_review"] += 1
                else:
                    provenance_counts["provisional"] += 1

                for pid, payload in payloads.items():
                    all_chunk_identities.append(
                        {
                            "qdrant_point_id": pid,
                            "document_id": payload["document_id"],
                            "chunk_id": payload["chunk_id"],
                            "content_hash": payload["content_hash"],
                        }
                    )

                if dry_run:
                    total_chunks += len(payloads)
                    processed_docs += 1
                    continue

                total_chunks += len(payloads)
                if skip_existing_points:
                    missing_payloads: dict[str, dict[str, Any]] = {}
                    for point_id, payload in payloads.items():
                        state, reason = check_existing_point_conflict(
                            point_id,
                            payload,
                            existing_fingerprints,
                        )
                        if state == "match":
                            skipped_existing_chunks += 1
                            record_skip(receipt, "already_present_matching_content", 1)
                        elif state == "conflict":
                            receipt["conflict_points"] += 1
                            conflicts.append(reason or f"conflict on {point_id}")
                            error_count += 1
                            fatal_error = (
                                f"Resume conflict at line {line_number}: {reason}. "
                                "Bỏ qua bị từ chối; hãy tạo staging release mới."
                            )
                            receipt["errors"].append({"line": line_number, "conflict": reason})
                            break
                        else:
                            missing_payloads[point_id] = payload

                    if fatal_error is not None:
                        break
                    if not missing_payloads:
                        processed_docs += 1
                        continue

                    vectors = embed_chunk_payloads(
                        missing_payloads,
                        embedding_batch_size=embedding_batch_size,
                        expected_vector_size=vector_size,
                    )
                else:
                    vectors = embed_chunk_payloads(
                        payloads,
                        embedding_batch_size=embedding_batch_size,
                        expected_vector_size=vector_size,
                    )

                vectors_batch.update(vectors)
                processed_docs += 1
                newly_embedded_chunks += len(vectors)

                if len(vectors_batch) >= batch_size:
                    _flush_batch(line_number)

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
                receipt["failed_points"] += 1
                receipt["errors"].append(
                    {"line": line_number, "error_type": type(exc).__name__, "error": str(exc)}
                )
                logger.exception("line %s: import failed: %s", line_number, exc)

        if vectors_batch and not dry_run and fatal_error is None:
            try:
                _flush_batch(last_processed_line)
            except ImportWriteError as exc:
                error_count += 1
                fatal_error = str(exc)
                logger.exception("Fatal Qdrant write error in final batch")

    finally:
        if lease_manager is not None and lease is not None:
            lease_manager.release_lease(lease)

    finalize_write_receipt(receipt)
    chunk_fp = compute_chunk_set_fingerprint(all_chunk_identities)
    overall_ok = bool(
        error_count == 0
        and fatal_error is None
        and not conflicts
        and receipt["ok"]
    )
    if not overall_ok and not dry_run:
        receipt["ok"] = False
        if receipt["status"] in {"committed", "skipped", "no_op", "acknowledged_unverified"}:
            receipt["status"] = "partial" if upserted_chunks > 0 else "failed"

    if not dry_run and overall_ok:
        logger.warning(
            "BM25 was not initialized by the importer because BM25 is an immutable artifact "
            "built per release and must match chunk_set_fingerprint=%s",
            chunk_fp["chunk_set_fingerprint"][:16],
        )

    result = {
        "status": overall_ok,
        "ok": overall_ok,
        "dry_run": dry_run,
        "topology_verified": admission["topology_verified"],
        "admission_warning": admission.get("warning"),
        "release_id": resolved_release_id,
        "data_file": str(data_path),
        "data_file_sha256": data_file_sha256,
        "collection_name": resolved_collection,
        "corpus_version": resolved_version or None,
        "embedding_config": emb_cfg,
        "resume_signature": resume_signature,
        "chunk_set_fingerprint": chunk_fp["chunk_set_fingerprint"],
        "unique_document_count": chunk_fp["unique_document_count"],
        "unique_chunk_count": chunk_fp["unique_chunk_count"],
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
        "trusted_source_metadata_required": require_trusted_source_metadata,
        "counts_by_content_type": counts_by_content_type,
        "provenance_counts": provenance_counts,
        "error_count": error_count,
        "conflict_count": len(conflicts),
        "conflicts_preview": conflicts[:20],
        "validation_errors_preview": validation_errors[:20],
        "fatal_error": fatal_error,
        "write_receipt": receipt,
    }
    write_import_manifest(manifest_path, result)

    if release_manifest_path is not None and not dry_run:
        release_manifest = build_release_manifest(
            corpus_version=resolved_version,
            physical_collection=resolved_collection,
            serving_alias=DEFAULT_COLLECTION_ALIAS,
            release_id=resolved_release_id,
            source_manifest={
                "path": str(data_path),
                "sha256": data_file_sha256,
                "document_count": processed_docs,
                "counts_by_content_type": counts_by_content_type,
            },
            chunk_manifest={
                "expected_count": total_chunks,
                "unique_document_count": chunk_fp["unique_document_count"],
                "unique_chunk_count": chunk_fp["unique_chunk_count"],
                "chunk_set_fingerprint": chunk_fp["chunk_set_fingerprint"],
            },
            chunking_config={
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "splitter_version": splitter_version,
            },
            embedding_config=emb_cfg,
            provenance_summary=provenance_counts,
            write_receipt={
                key: receipt[key]
                for key in (
                    "ok",
                    "status",
                    "attempted_points",
                    "acknowledged_points",
                    "committed_points",
                    "failed_points",
                    "unconfirmed_points",
                    "skipped_points",
                    "conflict_points",
                    "partial_write",
                    "rollback_performed",
                )
            },
            build_status="imported" if overall_ok else ("partial" if upserted_chunks > 0 else "failed"),
            publication_status="staging",
        )
        save_release_manifest(release_manifest_path, release_manifest)

    logger.info("Import result: status=%s upserted=%s errors=%s", overall_ok, upserted_chunks, error_count)
    return result


def import_qa_data(*args, **kwargs):
    """Backward-compatible alias cho code cũ."""
    return import_embedding_dataset(*args, **kwargs)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Health/InBody embedding_documents.jsonl into a staging Qdrant collection"
    )
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument(
        "--collection",
        default=None,
        help="Explicit physical staging collection name (never defaults to serving alias).",
    )
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
        help="Immutable corpus version stored in every payload (required for real imports).",
    )
    parser.add_argument(
        "--start-line",
        type=int,
        default=1,
        help="Resume from this 1-based JSONL line; requires compatible checkpoint if manifest exists.",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=None,
        help="Write an atomic JSON progress/final manifest & checkpoint.",
    )
    parser.add_argument(
        "--release-manifest-file",
        type=Path,
        default=None,
        help="Write a versioned corpus release manifest binding source, chunks, Qdrant, and embedding config.",
    )
    parser.add_argument(
        "--lock-dir",
        type=Path,
        default=None,
        help="Optional shared directory for staging write/activation locks.",
    )
    parser.add_argument(
        "--skip-existing-points",
        action="store_true",
        help=(
            "Scan target point fingerprints (ID + content_hash + version) and embed only missing chunks. "
            "Conflicts on differing content_hash/version fail closed."
        ),
    )
    parser.add_argument(
        "--require-trusted-source-metadata",
        action="store_true",
        help=(
            "Fail validation unless source URL, publisher, tier, publish/review dates "
            "and registry-verified approved medical review status are present."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
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
            release_manifest_file=args.release_manifest_file,
            skip_existing_points=args.skip_existing_points,
            require_trusted_source_metadata=args.require_trusted_source_metadata,
            lock_dir=args.lock_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": False,
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

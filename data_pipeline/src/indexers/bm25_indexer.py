"""Module Xuất và Đóng gói Snapshot BM25 (BM25 Snapshot Indexer).

Vai trò:
    Tạo ra file artifact nén gzip (`bm25_snapshot.json.gz`) gắn chặt với một corpus release:
    - Bắt buộc có `corpus_version` tường minh (không hard-code version).
    - Bảo toàn định danh canonical (`document_id`, `chunk_id`, `qdrant_point_id`, `content_hash`)
      và `chunk_set_fingerprint` để đối chiếu chính xác với Qdrant physical collection.
    - Ghi nguyên tử (temp file + fsync + os.replace) để runtime không bao giờ đọc file ghi dở.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..processors.lifecycle_bridge import (
    BM25_TOKENIZER_VERSION,
    CANONICAL_ID_SCHEMA_VERSION,
    compute_chunk_set_fingerprint,
    make_release_id,
    validate_corpus_version,
)
from ..processors.provenance_bridge import PROVENANCE_METADATA_FIELDS

logger = logging.getLogger(__name__)

BM25_SNAPSHOT_SCHEMA_VERSION = 1


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_bm25_documents_from_chunks(
    chunks: List[Dict[str, Any]],
    *,
    corpus_version: Optional[str] = None,
    release_id: Optional[str] = None,
    physical_collection: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Chuyển đổi danh sách chunks sang định dạng tài liệu chuẩn của backend BM25 engine.

    Bảo toàn rõ ràng:
    - `document_id`: ID tài liệu gốc (không thay bằng chunk_id)
    - `chunk_id`: ID chunk duy nhất
    - `qdrant_point_id`: UUID5(NAMESPACE_URL, chunk_id) khớp 1-1 với Qdrant
    - `content_hash`: SHA-256 của nội dung chunk
    """
    bm25_docs: List[Dict[str, Any]] = []

    for chunk in chunks:
        chunk_meta = dict(chunk.get("metadata") or {})
        document_id = str(
            chunk.get("document_id")
            or chunk_meta.get("document_id")
            or chunk.get("doc_id")
            or chunk_meta.get("doc_id")
            or ""
        ).strip()
        chunk_id = str(
            chunk.get("chunk_id")
            or chunk_meta.get("chunk_id")
            or document_id
            or ""
        ).strip()
        if not document_id:
            document_id = chunk_id
        point_id = str(
            chunk.get("qdrant_point_id")
            or chunk_meta.get("qdrant_point_id")
            or (str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)) if chunk_id else "")
        )
        content = str(chunk.get("content") or "")
        content_hash = str(
            chunk.get("content_hash")
            or chunk_meta.get("content_hash")
            or hashlib.sha256(content.encode("utf-8")).hexdigest()
        )

        provenance = {
            field: chunk.get(field) if field in chunk else chunk_meta.get(field)
            for field in PROVENANCE_METADATA_FIELDS
            if field in chunk or field in chunk_meta
        }
        if corpus_version:
            provenance["corpus_version"] = corpus_version
        provenance["document_id"] = document_id
        provenance["chunk_id"] = chunk_id
        provenance["content_hash"] = content_hash

        merged_meta = {
            **chunk_meta,
            **provenance,
            "qdrant_point_id": point_id,
        }
        if release_id:
            merged_meta["release_id"] = release_id
        if physical_collection:
            merged_meta["physical_collection"] = physical_collection

        doc_entry: Dict[str, Any] = {
            **provenance,
            # Legacy `doc_id` keeps chunk_id for BM25 result dedup compatibility while
            # `document_id`, `chunk_id`, and `qdrant_point_id` carry canonical identity.
            "doc_id": chunk_id or document_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "qdrant_point_id": point_id,
            "content_hash": content_hash,
            "question": chunk.get("title") or "",
            "title": chunk.get("title") or "",
            "content": content,
            "source": chunk.get("source") or "health_inbody_corpus",
            "content_type": chunk.get("content_type") or "general_health",
            "domain": chunk.get("domain") or "health_inbody",
            "parent_id": chunk.get("parent_id"),
            "parent_title": chunk.get("parent_title"),
            "parent_content": chunk.get("parent_content"),
            "has_parent": chunk.get("has_parent", False),
            "metadata": merged_meta,
        }
        if release_id:
            doc_entry["release_id"] = release_id
        if physical_collection:
            doc_entry["physical_collection"] = physical_collection
        bm25_docs.append(doc_entry)

    return bm25_docs


def export_bm25_snapshot(
    chunks: List[Dict[str, Any]],
    output_path: Path,
    collection_name: str = "nmk_chatbot_active",
    corpus_version: Optional[str] = None,
    *,
    physical_collection: Optional[str] = None,
    release_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    """Xây dựng và lưu trữ file snapshot BM25 nén gzip nguyên tử (fsync + atomic replace).

    Yêu cầu `corpus_version` tường minh (không hard-code version).
    Đính kèm `chunk_set_fingerprint`, `physical_collection`, `release_id`, `tokenizer_version`.
    """
    verified_version = validate_corpus_version(corpus_version)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_physical = str(physical_collection or "").strip() or None
    bm25_docs = build_bm25_documents_from_chunks(
        chunks,
        corpus_version=verified_version,
        release_id=release_id,
        physical_collection=resolved_physical,
    )
    fp_info = compute_chunk_set_fingerprint(bm25_docs)
    resolved_release_id = release_id or make_release_id(
        verified_version, fp_info["chunk_set_fingerprint"]
    )
    for doc in bm25_docs:
        doc.setdefault("release_id", resolved_release_id)
        if isinstance(doc.get("metadata"), dict):
            doc["metadata"].setdefault("release_id", resolved_release_id)

    created_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "corpus_version": verified_version,
        "release_id": resolved_release_id,
        "physical_collection": resolved_physical,
        "serving_alias": collection_name,
        "built_by": "data_pipeline",
        "chunk_count": len(chunks),
        "unique_chunk_count": fp_info["unique_chunk_count"],
        "unique_document_count": fp_info["unique_document_count"],
        "duplicate_chunk_ids": fp_info["duplicate_chunk_ids"],
        "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
        "tokenizer_version": BM25_TOKENIZER_VERSION,
        "canonical_id_schema": CANONICAL_ID_SCHEMA_VERSION,
        **(extra_metadata or {}),
    }

    payload = {
        "schema_version": BM25_SNAPSHOT_SCHEMA_VERSION,
        "collection_name": collection_name,
        "physical_collection": resolved_physical,
        "release_id": resolved_release_id,
        "corpus_version": verified_version,
        "created_at": created_at,
        "document_count": len(bm25_docs),
        "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
        "metadata": metadata,
        "documents": bm25_docs,
    }

    fd, tmp_name = tempfile.mkstemp(
        dir=str(output_path.parent),
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as raw_handle:
            with gzip.GzipFile(fileobj=raw_handle, mode="wb") as gz_handle:
                encoded = json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
                gz_handle.write(encoded)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        os.replace(temporary_path, output_path)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    artifact_sha256 = _sha256_file(output_path)
    file_size_kb = output_path.stat().st_size / 1024.0
    logger.info(
        "Exported BM25 snapshot to %s: %s documents (%.1f KB, fp=%s)",
        output_path,
        len(bm25_docs),
        file_size_kb,
        fp_info["chunk_set_fingerprint"][:16],
    )

    return {
        "status": "ok",
        "output_path": str(output_path),
        "sha256": artifact_sha256,
        "document_count": len(bm25_docs),
        "unique_document_count": fp_info["unique_document_count"],
        "unique_chunk_count": fp_info["unique_chunk_count"],
        "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
        "collection_name": collection_name,
        "physical_collection": resolved_physical,
        "release_id": resolved_release_id,
        "corpus_version": verified_version,
        "schema_version": BM25_SNAPSHOT_SCHEMA_VERSION,
        "tokenizer_version": BM25_TOKENIZER_VERSION,
        "created_at": created_at,
        "file_size_kb": round(file_size_kb, 1),
    }

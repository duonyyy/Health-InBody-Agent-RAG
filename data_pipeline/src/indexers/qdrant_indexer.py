"""Module Nạp và Quản lý Chỉ mục Cơ sở dữ liệu Vector Qdrant (Qdrant Indexer).

Áp dụng cùng chính sách staging admission, write lease, kiểm tra vector trước upsert,
resume theo content_hash/version và WriteReceipt trung thực với backend importer.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from ..processors.lifecycle_bridge import (
    CorpusLeaseManager,
    check_existing_point_conflict,
    compute_chunk_set_fingerprint,
    current_embedding_config,
    finalize_write_receipt,
    interpret_qdrant_upsert_result,
    make_release_id,
    new_write_receipt,
    record_skip,
    validate_embeddings_alignment,
    verify_staging_write_target,
)
from ..processors.provenance_bridge import PROVENANCE_METADATA_FIELDS

logger = logging.getLogger(__name__)

INDEX_KEYWORD_FIELDS = [
    "content_type",
    "domain",
    "source",
    "parent_id",
    "doc_id",
    "document_id",
    "chunk_id",
    "content_hash",
    "medical_review_status",
    "review_verification_status",
    "corpus_version",
    "release_id",
    "embedding_fingerprint",
]

_FINGERPRINT_FIELDS = [
    "doc_id",
    "document_id",
    "chunk_id",
    "content_hash",
    "corpus_version",
    "release_id",
    "embedding_fingerprint",
]


class QdrantIndexer:
    """Quản trị viên kết nối và nạp vector vào physical staging Qdrant Collection."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        timeout: float = 30.0,
        vector_size: int = 1024,
        lock_dir: Optional[str | Path] = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.vector_size = vector_size
        self.lock_dir = lock_dir
        self._client: Optional[QdrantClient] = None

    @property
    def client(self) -> QdrantClient:
        """Tạo hoặc tái sử dụng instance QdrantClient kết nối tới server."""
        if self._client is None:
            self._client = QdrantClient(
                url=self.url,
                timeout=self.timeout,
                check_compatibility=False,
            )
        return self._client

    def is_available(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def create_collection_if_missing(
        self,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
    ) -> bool:
        """Tạo mới physical staging collection nếu chưa tồn tại (fail-closed staging guard)."""
        verify_staging_write_target(
            collection_name,
            qdrant_client=self.client,
            require_corpus_version=False,
            require_allowlist=False,
            dry_run=False,
        )
        size = vector_size or self.vector_size
        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name in collections:
            logger.info("Qdrant staging collection '%s' already exists", collection_name)
            return False

        self.client.create_collection(
            collection_name=str(collection_name),
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant staging collection '%s' (dim=%s, metric=Cosine)", collection_name, size)
        self.ensure_payload_indexes(str(collection_name))
        return True

    def ensure_payload_indexes(self, collection_name: str) -> Dict[str, str]:
        results = {}
        try:
            collection_info = self.client.get_collection(collection_name)
            existing_fields = set((collection_info.payload_schema or {}).keys())
        except Exception:
            existing_fields = set()

        for field in INDEX_KEYWORD_FIELDS:
            if field in existing_fields:
                results[field] = "exists"
                continue
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                    wait=True,
                )
                results[field] = "created"
            except Exception as exc:
                results[field] = f"error: {exc}"
        return results

    def get_existing_point_ids(self, collection_name: str) -> Set[str]:
        return set(self.get_existing_point_fingerprints(collection_name).keys())

    def get_existing_point_fingerprints(self, collection_name: str) -> Dict[str, Dict[str, Any]]:
        """Cuộn (scroll) ID + content_hash + version để resume an toàn không bỏ sót xung đột."""
        fingerprints: Dict[str, Dict[str, Any]] = {}
        next_offset = None
        while True:
            page, next_offset = self.client.scroll(
                collection_name=collection_name,
                limit=500,
                offset=next_offset,
                with_payload=_FINGERPRINT_FIELDS,
                with_vectors=False,
            )
            for point in page or []:
                pid = str(point.id)
                payload = dict(point.payload or {})
                fingerprints[pid] = {
                    "qdrant_point_id": pid,
                    "doc_id": payload.get("doc_id"),
                    "document_id": payload.get("document_id") or payload.get("doc_id"),
                    "chunk_id": payload.get("chunk_id") or payload.get("doc_id") or pid,
                    "content_hash": payload.get("content_hash"),
                    "corpus_version": payload.get("corpus_version"),
                    "release_id": payload.get("release_id"),
                    "embedding_fingerprint": payload.get("embedding_fingerprint"),
                }
            if next_offset is None or not page:
                break
        return fingerprints

    def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embedder: Any,
        collection_name: Optional[str] = None,
        batch_size: int = 50,
        skip_existing: bool = True,
        dry_run: bool = False,
        *,
        corpus_version: Optional[str] = None,
        release_id: Optional[str] = None,
        embedding_model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tạo vector embedding và nạp batch các chunk vào physical staging Qdrant collection.

        - R06: Chặn serving alias và physical target đang phục vụ (fail-closed).
        - R12: Kiểm alignment/dimension/finite trước upsert; trả WriteReceipt trung thực.
        - Resume: Kiểm cả content_hash, corpus_version và embedding_fingerprint; báo conflict nếu khác.
        - Dry-run: Tuyệt đối không ghi vector giả vào collection Qdrant thật.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        # R06: Unified staging admission gate BEFORE any embed/write.
        admission = verify_staging_write_target(
            collection_name,
            qdrant_client=None if dry_run else self.client,
            corpus_version=corpus_version,
            require_corpus_version=not dry_run,
            require_allowlist=False,
            dry_run=dry_run,
        )
        resolved_collection = admission["target_collection"]
        resolved_version = admission["corpus_version"] or ""

        emb_cfg = current_embedding_config(
            vector_size=self.vector_size,
            model_identifier=embedding_model_id,
        )
        embedding_fingerprint = emb_cfg["fingerprint"]
        fp_info = compute_chunk_set_fingerprint(chunks)
        resolved_release_id = release_id or make_release_id(
            resolved_version or "dry-run",
            fp_info["chunk_set_fingerprint"],
        )

        receipt = new_write_receipt(
            collection_name=resolved_collection,
            corpus_version=resolved_version or None,
            release_id=resolved_release_id,
            dry_run=dry_run,
        )

        if not chunks:
            finalize_write_receipt(receipt)
            return {
                **receipt,
                "status": "empty",
                "total_chunks": 0,
                "indexed_points": 0,
                "validated_points": 0,
                "topology_verified": admission["topology_verified"],
                "admission_warning": admission.get("warning"),
            }

        lease_manager: Optional[CorpusLeaseManager] = None
        lease = None
        if not dry_run:
            lease_manager = CorpusLeaseManager(lock_dir=self.lock_dir)
            lease = lease_manager.acquire_write_lease(
                resolved_collection,
                qdrant_client=self.client,
                corpus_version=resolved_version,
                release_id=resolved_release_id,
                require_corpus_version=True,
            )

        validated_points = 0
        total_batches = 0
        conflicts: List[str] = []

        try:
            existing_fingerprints: Dict[str, Dict[str, Any]] = {}
            if not dry_run and skip_existing:
                existing_fingerprints = self.get_existing_point_fingerprints(resolved_collection)

            points_to_index: List[Dict[str, Any]] = []
            for chunk in chunks:
                chunk_meta = dict(chunk.get("metadata") or {})
                document_id = str(
                    chunk.get("document_id")
                    or chunk_meta.get("document_id")
                    or chunk.get("doc_id")
                    or chunk_meta.get("doc_id")
                    or ""
                ).strip()
                chunk_id = str(chunk.get("chunk_id") or document_id).strip()
                if not document_id:
                    document_id = chunk_id
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
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
                payload = {
                    **chunk_meta,
                    **provenance,
                    "doc_id": chunk.get("doc_id", document_id),
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "parent_id": chunk.get("parent_id"),
                    "parent_title": chunk.get("parent_title"),
                    "parent_content": chunk.get("parent_content"),
                    "has_parent": chunk.get("has_parent", False),
                    "title": chunk.get("title") or "",
                    "question": chunk.get("title") or "",
                    "content": content,
                    "text": content,
                    "source": chunk.get("source") or "health_inbody_corpus",
                    "content_type": chunk.get("content_type") or "general_health",
                    "domain": chunk.get("domain") or "health_inbody",
                    "breadcrumb": chunk.get("breadcrumb"),
                    "content_hash": content_hash,
                    "qdrant_point_id": point_id,
                    "corpus_version": resolved_version or chunk.get("corpus_version"),
                    "release_id": resolved_release_id,
                    "embedding_fingerprint": embedding_fingerprint,
                }

                if not dry_run and skip_existing:
                    state, reason = check_existing_point_conflict(
                        point_id,
                        payload,
                        existing_fingerprints,
                    )
                    if state == "match":
                        record_skip(receipt, "already_present_matching_content", 1)
                        continue
                    if state == "conflict":
                        receipt["conflict_points"] += 1
                        conflicts.append(reason or f"conflict on {point_id}")
                        receipt["errors"].append({"chunk_id": chunk_id, "conflict": reason})
                        continue

                points_to_index.append(
                    {
                        "point_id": point_id,
                        "payload": payload,
                        "text": content,
                    }
                )

            if conflicts:
                finalize_write_receipt(receipt)
                return {
                    **receipt,
                    "total_chunks": len(chunks),
                    "indexed_points": 0,
                    "validated_points": 0,
                    "skipped_points": receipt["skipped_points"],
                    "conflicts": conflicts[:20],
                    "batch_count": 0,
                    "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
                    "topology_verified": admission["topology_verified"],
                    "admission_warning": admission.get("warning"),
                }

            if not points_to_index:
                finalize_write_receipt(receipt)
                return {
                    **receipt,
                    "status": "up_to_date",
                    "total_chunks": len(chunks),
                    "indexed_points": 0,
                    "validated_points": 0,
                    "skipped_points": receipt["skipped_points"],
                    "batch_count": 0,
                    "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
                    "topology_verified": admission["topology_verified"],
                    "admission_warning": admission.get("warning"),
                }

            total_batches = (len(points_to_index) + batch_size - 1) // batch_size
            for b_idx in range(0, len(points_to_index), batch_size):
                batch_num = (b_idx // batch_size) + 1
                batch_items = points_to_index[b_idx : b_idx + batch_size]
                batch_texts = [item["text"] for item in batch_items]

                if dry_run:
                    # Validate payloads & simulated embedding alignment ONLY; never call Qdrant upsert.
                    mock_vectors = embedder.embed_texts(batch_texts, dry_run=True)
                    validate_embeddings_alignment(
                        batch_items,
                        mock_vectors,
                        expected_vector_size=self.vector_size,
                    )
                    validated_points += len(batch_items)
                    continue

                receipt["batches_attempted"] += 1
                receipt["attempted_points"] += len(batch_items)
                try:
                    # Re-verify lease & live alias topology right before EVERY batch upsert.
                    if lease is not None and lease_manager is not None:
                        lease_manager.verify_and_renew_write_lease(
                            lease,
                            qdrant_client=self.client,
                        )

                    embeddings = embedder.embed_texts(batch_texts, dry_run=False)
                    validated_vectors = validate_embeddings_alignment(
                        batch_items,
                        embeddings,
                        expected_vector_size=self.vector_size,
                    )
                    qdrant_points = [
                        PointStruct(
                            id=item["point_id"],
                            vector=vec,
                            payload=item["payload"],
                        )
                        for item, vec in zip(batch_items, validated_vectors)
                    ]

                    raw_result = self.client.upsert(
                        collection_name=resolved_collection,
                        points=qdrant_points,
                        wait=True,
                    )
                    state, detail = interpret_qdrant_upsert_result(raw_result)
                    if state == "committed":
                        receipt["batches_committed"] += 1
                        receipt["acknowledged_points"] += len(qdrant_points)
                        receipt["committed_points"] += len(qdrant_points)
                        validated_points += len(qdrant_points)
                        receipt["batch_receipts"].append(
                            {"batch": batch_num, "point_count": len(qdrant_points), "status": "committed"}
                        )
                    elif state == "unverified_client_return":
                        receipt["batches_committed"] += 1
                        receipt["acknowledged_points"] += len(qdrant_points)
                        validated_points += len(qdrant_points)
                        receipt["batch_receipts"].append(
                            {
                                "batch": batch_num,
                                "point_count": len(qdrant_points),
                                "status": "acknowledged_unverified",
                                "detail": detail,
                            }
                        )
                    elif state == "acknowledged_uncommitted":
                        receipt["batches_unconfirmed"] += 1
                        receipt["acknowledged_points"] += len(qdrant_points)
                        receipt["unconfirmed_points"] += len(qdrant_points)
                        err = {
                            "batch": batch_num,
                            "point_count": len(qdrant_points),
                            "status": "acknowledged_uncommitted",
                            "error": detail,
                        }
                        receipt["errors"].append(err)
                        receipt["batch_receipts"].append(err)
                        break
                    else:
                        receipt["batches_failed"] += 1
                        receipt["failed_points"] += len(qdrant_points)
                        err = {
                            "batch": batch_num,
                            "point_count": len(qdrant_points),
                            "status": "failed",
                            "error": detail,
                        }
                        receipt["errors"].append(err)
                        receipt["batch_receipts"].append(err)
                        break
                except Exception as exc:
                    receipt["batches_failed"] += 1
                    receipt["failed_points"] += len(batch_items)
                    err = {
                        "batch": batch_num,
                        "point_count": len(batch_items),
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    receipt["errors"].append(err)
                    receipt["batch_receipts"].append(err)
                    break
        finally:
            if lease_manager is not None and lease is not None:
                lease_manager.release_lease(lease)

        finalize_write_receipt(receipt)
        actual_indexed = (
            0
            if dry_run
            else int(receipt["committed_points"] or receipt["acknowledged_points"] or 0)
        )
        return {
            **receipt,
            "total_chunks": len(chunks),
            "indexed_points": actual_indexed,
            "validated_points": validated_points,
            "batch_count": total_batches,
            "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
            "embedding_config": emb_cfg,
            "topology_verified": admission["topology_verified"],
            "admission_warning": admission.get("warning"),
        }

"""Các thao tác với vector database Qdrant (có staging admission, write receipt và activation lock)."""
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Range,
    VectorParams,
)

from core.config import (
    DEFAULT_QDRANT_SEARCH_TIMEOUT,
    DEFAULT_QDRANT_TIMEOUT,
    DEFAULT_QDRANT_URL,
    DEFAULT_VECTOR_SIZE,
)
from harness.budget import (
    BudgetExhaustedError,
    call_with_supported_kwargs,
    remaining_for_call,
)
from rag.corpus_lifecycle import (
    CorpusLease,
    CorpusLeaseManager,
    QdrantWriteError,
    check_release_activation_ready,
    compute_chunk_set_fingerprint,
    finalize_write_receipt,
    interpret_qdrant_upsert_result,
    load_release_manifest,
    new_write_receipt,
    save_release_manifest,
    validate_vectors_before_upsert,
    verify_staging_write_target,
)
from rag.vector_metadata import (
    PAYLOAD_KEYWORD_INDEX_FIELDS,
    detect_content_type,
    prepare_vector_payload,
)

logger = logging.getLogger(__name__)


def _create_qdrant_client(url: str, timeout: float) -> QdrantClient:
    """Create a QdrantClient without triggering an unbudgeted startup version probe."""
    return call_with_supported_kwargs(
        QdrantClient,
        url=url,
        timeout=timeout,
        check_compatibility=False,
    )


client = _create_qdrant_client(
    url=DEFAULT_QDRANT_URL,
    timeout=DEFAULT_QDRANT_TIMEOUT,
)
search_client = _create_qdrant_client(
    url=DEFAULT_QDRANT_URL,
    timeout=DEFAULT_QDRANT_SEARCH_TIMEOUT,
)


def _active_client(qdrant_client: Any = None) -> Any:
    return client if qdrant_client is None else qdrant_client


def create_collection(
    name,
    vector_size=DEFAULT_VECTOR_SIZE,
    *,
    qdrant_client: Any = None,
    enforce_staging_policy: bool = True,
    protected_aliases: Optional[Iterable[str]] = None,
    require_allowlist: bool = False,
):
    """
    Tạo physical staging collection mới trong Qdrant để lưu embedding/vector.

    Mọi yêu cầu tạo collection đều phải qua staging admission (chặn serving alias
    và physical target đang phục vụ; fail-closed khi không xác minh được topology).
    """
    active = _active_client(qdrant_client)
    if enforce_staging_policy:
        verify_staging_write_target(
            name,
            qdrant_client=active,
            require_corpus_version=False,
            require_allowlist=require_allowlist,
            protected_aliases=protected_aliases,
            dry_run=False,
        )
    result = active.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    ensure_payload_indexes(name, raise_on_error=True, qdrant_client=active)
    return result


def ensure_payload_indexes(collection_name, raise_on_error=False, *, qdrant_client: Any = None):
    """Ensure fields used by retrieval filters have Qdrant keyword indexes."""
    active = _active_client(qdrant_client)
    results = {}
    errors = {}

    try:
        collection_info = active.get_collection(collection_name)
        existing_fields = set((collection_info.payload_schema or {}).keys())
    except Exception as exc:
        if raise_on_error:
            raise RuntimeError(
                f"Could not inspect Qdrant collection {collection_name}: {exc}"
            ) from exc
        logger.warning("Could not inspect collection %s: %s", collection_name, exc)
        existing_fields = set()

    for field_name in PAYLOAD_KEYWORD_INDEX_FIELDS:
        if field_name in existing_fields:
            results[field_name] = "existing"
            continue
        try:
            results[field_name] = active.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )
        except Exception as exc:
            errors[field_name] = str(exc)
            logger.warning(
                "Could not ensure payload index %s.%s: %s",
                collection_name,
                field_name,
                exc,
            )

    if errors and raise_on_error:
        raise RuntimeError(
            f"Could not create required Qdrant payload indexes: {errors}"
        )

    return {"created_or_existing": results, "errors": errors}


def add_vector(
    collection_name,
    vectors=None,
    batch_size=100,
    raise_on_error=False,
    *,
    expected_vector_size: Optional[int] = None,
    corpus_version: Optional[str] = None,
    release_id: Optional[str] = None,
    embedding_fingerprint: Optional[str] = None,
    enforce_staging_policy: bool = True,
    require_corpus_version: bool = False,
    require_allowlist: bool = False,
    protected_aliases: Optional[Iterable[str]] = None,
    require_canonical_payload: bool = False,
    lease: Optional[CorpusLease] = None,
    lease_manager: Optional[CorpusLeaseManager] = None,
    qdrant_client: Any = None,
) -> Dict[str, Any]:
    """
    Thêm hoặc cập nhật nhiều vector vào một physical staging collection.

    Trả về WriteReceipt trung thực (phân biệt attempted, acknowledged, committed,
    unconfirmed, failed, partial_write). Không bao giờ nuốt lỗi batch thành thành công.
    """
    active = _active_client(qdrant_client)
    receipt = new_write_receipt(
        collection_name=str(collection_name or ""),
        corpus_version=corpus_version,
        release_id=release_id,
        dry_run=False,
    )

    if enforce_staging_policy:
        verify_staging_write_target(
            collection_name,
            qdrant_client=active,
            corpus_version=corpus_version,
            require_corpus_version=require_corpus_version,
            require_allowlist=require_allowlist,
            protected_aliases=protected_aliases,
            dry_run=False,
        )

    if not vectors:
        return finalize_write_receipt(receipt)
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    # Pre-upsert validation: IDs, exact dimension, finite coordinates, payload invariants.
    validate_vectors_before_upsert(
        vectors,
        expected_vector_size=expected_vector_size,
        expected_corpus_version=corpus_version,
        expected_embedding_fingerprint=embedding_fingerprint,
        require_canonical_payload=require_canonical_payload,
    )

    points = []
    for point_id, value in vectors.items():
        prepared_payload = prepare_vector_payload(value["payload"])
        if corpus_version and not prepared_payload.get("corpus_version"):
            prepared_payload["corpus_version"] = corpus_version
        if release_id and not prepared_payload.get("release_id"):
            prepared_payload["release_id"] = release_id
        if embedding_fingerprint and not prepared_payload.get("embedding_fingerprint"):
            prepared_payload["embedding_fingerprint"] = embedding_fingerprint
        points.append(
            PointStruct(
                id=point_id,
                vector=[float(x) for x in value["vector"]],
                payload=prepared_payload,
            )
        )

    total_batches = (len(points) - 1) // batch_size + 1
    for i in range(0, len(points), batch_size):
        batch_num = i // batch_size + 1
        batch = points[i : i + batch_size]
        batch_ids = [str(point.id) for point in batch]
        receipt["batches_attempted"] += 1
        receipt["attempted_points"] += len(batch)

        try:
            # Re-verify lease & live alias topology right before EVERY batch upsert.
            if lease is not None and lease_manager is not None:
                lease_manager.verify_and_renew_write_lease(
                    lease,
                    qdrant_client=active,
                    protected_aliases=protected_aliases,
                )
            elif enforce_staging_policy and batch_num > 1:
                verify_staging_write_target(
                    collection_name,
                    qdrant_client=active,
                    corpus_version=corpus_version,
                    require_corpus_version=require_corpus_version,
                    require_allowlist=require_allowlist,
                    protected_aliases=protected_aliases,
                    dry_run=False,
                )

            raw_result = active.upsert(
                collection_name=collection_name,
                wait=True,
                points=batch,
            )
            state, detail = interpret_qdrant_upsert_result(raw_result)
            if state == "committed":
                receipt["batches_committed"] += 1
                receipt["acknowledged_points"] += len(batch)
                receipt["committed_points"] += len(batch)
                receipt["batch_receipts"].append(
                    {
                        "batch": batch_num,
                        "point_count": len(batch),
                        "status": "committed",
                        "server_status": detail,
                        "operation_id": getattr(raw_result, "operation_id", None),
                    }
                )
                logger.info("Committed batch %s/%s (%s points)", batch_num, total_batches, len(batch))
            elif state == "unverified_client_return":
                receipt["batches_committed"] += 1
                receipt["acknowledged_points"] += len(batch)
                receipt["batch_receipts"].append(
                    {
                        "batch": batch_num,
                        "point_count": len(batch),
                        "status": "acknowledged_unverified",
                        "detail": detail,
                    }
                )
                logger.warning(
                    "Batch %s/%s returned without Qdrant UpdateResult status (%s)",
                    batch_num,
                    total_batches,
                    detail,
                )
            elif state == "acknowledged_uncommitted":
                receipt["batches_unconfirmed"] += 1
                receipt["acknowledged_points"] += len(batch)
                receipt["unconfirmed_points"] += len(batch)
                err = {
                    "batch": batch_num,
                    "point_count": len(batch),
                    "status": "acknowledged_uncommitted",
                    "error": detail or "Qdrant returned acknowledged instead of completed",
                }
                receipt["errors"].append(err)
                receipt["batch_receipts"].append(err)
                logger.error("Batch %s/%s unconfirmed under wait=True: %s", batch_num, total_batches, detail)
                if raise_on_error:
                    break
            else:
                receipt["batches_failed"] += 1
                receipt["failed_points"] += len(batch)
                err = {
                    "batch": batch_num,
                    "point_count": len(batch),
                    "point_ids_preview": batch_ids[:5],
                    "status": "failed",
                    "error": detail or "Qdrant upsert did not complete",
                }
                receipt["errors"].append(err)
                receipt["batch_receipts"].append(err)
                logger.error("Failed batch %s/%s: %s", batch_num, total_batches, detail)
                if raise_on_error:
                    break
        except Exception as e:
            logger.error("Failed to process batch %s/%s: %s", batch_num, total_batches, e)
            receipt["batches_failed"] += 1
            receipt["failed_points"] += len(batch)
            err = {
                "batch": batch_num,
                "point_count": len(batch),
                "point_ids_preview": batch_ids[:5],
                "status": "failed",
                "error_type": type(e).__name__,
                "error": str(e),
            }
            receipt["errors"].append(err)
            receipt["batch_receipts"].append(err)
            if raise_on_error:
                break

    finalize_write_receipt(receipt)

    if not receipt["ok"] and raise_on_error:
        raise QdrantWriteError(
            f"Qdrant upsert failed/incomplete for {collection_name!r}: "
            f"committed={receipt['committed_points']}, failed={receipt['failed_points']}, "
            f"unconfirmed={receipt['unconfirmed_points']}",
            receipt=receipt,
        )

    return receipt


def search_vector(
    collection_name,
    vector,
    limit=4,
    filters=None,
    score_threshold=0.0,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    raise_on_timeout: bool = False,
    *,
    qdrant_client: Any = None,
    raise_on_error: bool = False,
):
    """
    Tìm kiếm các tài liệu gần nhất với query vector trong Qdrant.
    """
    active_search = search_client if qdrant_client is None else qdrant_client
    effective_timeout = remaining_for_call(
        deadline_monotonic,
        DEFAULT_QDRANT_SEARCH_TIMEOUT if timeout is None else timeout,
        default_timeout=DEFAULT_QDRANT_SEARCH_TIMEOUT,
        min_timeout=1.0,
    )
    if effective_timeout is None:
        logger.warning("Qdrant search skipped because remaining budget < 1.0s")
        if raise_on_timeout or raise_on_error:
            raise BudgetExhaustedError("Qdrant search budget exhausted")
        return []
    # Qdrant SDK accepts integer timeout seconds; floor so timeout never exceeds remaining budget.
    qdrant_timeout = max(1, int(math.floor(effective_timeout)))

    try:
        filter_conditions = None
        if filters:
            conditions = []

            for field, value in filters.items():
                if isinstance(value, dict):
                    if (
                        "gte" in value
                        or "lte" in value
                        or "gt" in value
                        or "lt" in value
                    ):
                        range_filter = Range()
                        if "gte" in value:
                            range_filter.gte = value["gte"]
                        if "lte" in value:
                            range_filter.lte = value["lte"]
                        if "gt" in value:
                            range_filter.gt = value["gt"]
                        if "lt" in value:
                            range_filter.lt = value["lt"]

                        conditions.append(FieldCondition(key=field, range=range_filter))
                elif isinstance(value, (list, tuple, set)):
                    conditions.append(
                        FieldCondition(key=field, match=MatchAny(any=list(value)))
                    )
                else:
                    conditions.append(
                        FieldCondition(key=field, match=MatchValue(value=value))
                    )

            if conditions:
                filter_conditions = Filter(must=conditions)

        if hasattr(active_search, "search"):
            results = call_with_supported_kwargs(
                active_search.search,
                collection_name=collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=filter_conditions,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
                timeout=qdrant_timeout,
            )
        else:
            response = call_with_supported_kwargs(
                active_search.query_points,
                collection_name=collection_name,
                query=vector,
                limit=limit,
                query_filter=filter_conditions,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
                timeout=qdrant_timeout,
            )
            results = getattr(response, "points", response) or []

        processed_results = []
        for result in results:
            doc = dict(result.payload or {})
            doc["similarity_score"] = result.score
            doc["search_rank"] = len(processed_results) + 1
            processed_results.append(doc)

        logger.info(
            f"Vector search returned {len(processed_results)} results "
            f"(filtered from {len(results)} candidates)"
        )

        return processed_results

    except Exception as e:
        is_timeout = isinstance(e, (BudgetExhaustedError, TimeoutError)) or "timeout" in type(e).__name__.lower()
        logger.error("Vector search failed (%s)", type(e).__name__)
        if raise_on_timeout and is_timeout:
            raise BudgetExhaustedError("Qdrant vector search timed out") from e
        if raise_on_error:
            from rag.retrieval_errors import RetrievalDependencyError
            if is_timeout:
                raise BudgetExhaustedError("Qdrant vector search timed out") from e
            raise RetrievalDependencyError("qdrant_unavailable") from e
        return []


def search_with_multiple_vectors(collection_name, vectors, limit=4, filters=None):
    """Tìm kiếm bằng nhiều query vector và gộp kết quả."""
    all_results = []
    seen_content_keys = set()

    for i, vector in enumerate(vectors):
        try:
            results = search_vector(collection_name, vector, limit, filters)

            for result in results:
                content_key = result.get("content", "").strip().lower()
                if content_key not in seen_content_keys:
                    seen_content_keys.add(content_key)
                    result["query_vector_index"] = i
                    all_results.append(result)

        except Exception as e:
            logger.error(f"Search with vector {i} failed: {e}")
            continue

    all_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
    return all_results[:limit]


def get_collection_stats(collection_name, *, qdrant_client: Any = None):
    """Lấy thông tin thống kê/trạng thái của một collection trong Qdrant."""
    active = _active_client(qdrant_client)
    try:
        info = active.get_collection(collection_name)
        vectors_config = info.config.params.vectors
        return {
            "name": collection_name,
            "vector_size": getattr(vectors_config, "size", None),
            "vectors_count": getattr(info, "vectors_count", None),
            "indexed_vectors_count": getattr(info, "indexed_vectors_count", None),
            "points_count": info.points_count,
            "status": str(getattr(info.status, "value", info.status)),
            "optimizer_status": str(info.optimizer_status),
            "payload_indexes": sorted((info.payload_schema or {}).keys()),
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": str(e)}


def get_collection_point_ids(collection_name, batch_size=1000, *, qdrant_client: Any = None):
    """Load every point ID from a collection without transferring payload/vector data."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    active = _active_client(qdrant_client)
    point_ids = set()
    offset = None
    while True:
        points, next_offset = active.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        point_ids.update(str(point.id) for point in points)
        if next_offset is None:
            break
        offset = next_offset

    return point_ids


_FINGERPRINT_PAYLOAD_FIELDS = [
    "doc_id",
    "document_id",
    "chunk_id",
    "qdrant_point_id",
    "content_hash",
    "corpus_version",
    "release_id",
    "embedding_fingerprint",
]


def get_collection_point_fingerprints(
    collection_name: str,
    batch_size: int = 1000,
    *,
    qdrant_client: Any = None,
) -> Dict[str, Dict[str, Any]]:
    """Load minimal canonical identity/hash/version metadata per point ID for safe resume & verification."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    active = _active_client(qdrant_client)
    fingerprints: Dict[str, Dict[str, Any]] = {}
    offset = None
    while True:
        points, next_offset = active.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=_FINGERPRINT_PAYLOAD_FIELDS,
            with_vectors=False,
        )
        for point in points or []:
            pid = str(point.id)
            payload = dict(point.payload or {})
            fingerprints[pid] = {
                "qdrant_point_id": pid,
                "doc_id": payload.get("doc_id"),
                "document_id": payload.get("document_id"),
                "chunk_id": payload.get("chunk_id"),
                "content_hash": payload.get("content_hash"),
                "corpus_version": payload.get("corpus_version"),
                "release_id": payload.get("release_id"),
                "embedding_fingerprint": payload.get("embedding_fingerprint"),
            }
        if next_offset is None or not points:
            break
        offset = next_offset
    return fingerprints


def verify_collection_integrity(
    collection_name: str,
    *,
    expected_points: Optional[int] = None,
    expected_vector_size: Optional[int] = None,
    expected_chunk_set_fingerprint: Optional[str] = None,
    expected_corpus_version: Optional[str] = None,
    expected_embedding_fingerprint: Optional[str] = None,
    require_payload_indexes: bool = False,
    qdrant_client: Any = None,
) -> Dict[str, Any]:
    """Verify Qdrant collection stats, vector config, count, AND canonical ID/hash fingerprint.

    Never relies on collection status=='green' or point count alone when fingerprint/version
    expectations are supplied.
    """
    active = _active_client(qdrant_client)
    stats = get_collection_stats(collection_name, qdrant_client=active)
    if "error" in stats:
        raise RuntimeError(stats["error"])

    errors = []
    points_count = int(stats.get("points_count") or 0)
    if expected_points is not None and points_count != int(expected_points):
        errors.append(f"Point count mismatch: expected {expected_points}, found {points_count}")
    if expected_vector_size is not None and stats.get("vector_size") != int(expected_vector_size):
        errors.append(
            f"Vector size mismatch: expected {expected_vector_size}, found {stats.get('vector_size')}"
        )

    fingerprints = get_collection_point_fingerprints(collection_name, qdrant_client=active)
    fp_summary = compute_chunk_set_fingerprint(fingerprints.values())

    if len(fingerprints) != points_count:
        errors.append(
            f"Scrolled point count ({len(fingerprints)}) differs from collection stats ({points_count})"
        )

    if expected_chunk_set_fingerprint and fp_summary["chunk_set_fingerprint"] != expected_chunk_set_fingerprint:
        errors.append(
            "Collection chunk_set_fingerprint mismatch: "
            f"actual={fp_summary['chunk_set_fingerprint'][:16]} != expected={expected_chunk_set_fingerprint[:16]}"
        )

    versions_found = sorted(
        {str(item.get("corpus_version") or "").strip() for item in fingerprints.values()} - {""}
    )
    if expected_corpus_version:
        missing_ver = sum(
            1 for item in fingerprints.values()
            if str(item.get("corpus_version") or "").strip() != expected_corpus_version
        )
        if missing_ver:
            errors.append(
                f"{missing_ver} point(s) do not carry expected corpus_version={expected_corpus_version!r} "
                f"(found={versions_found})"
            )

    if expected_embedding_fingerprint:
        wrong_emb = sum(
            1 for item in fingerprints.values()
            if str(item.get("embedding_fingerprint") or "").strip() != expected_embedding_fingerprint
        )
        if wrong_emb:
            errors.append(
                f"{wrong_emb} point(s) do not match expected embedding_fingerprint={expected_embedding_fingerprint[:12]}"
            )

    if require_payload_indexes:
        existing_indexes = set(stats.get("payload_indexes") or [])
        required = {"content_type", "document_id", "corpus_version", "content_hash"}
        missing_idx = sorted(required - existing_indexes)
        if missing_idx:
            errors.append(f"Missing required payload indexes: {missing_idx}")

    result = {
        **stats,
        "scrolled_points": len(fingerprints),
        "chunk_set_fingerprint": fp_summary["chunk_set_fingerprint"],
        "unique_chunk_count": fp_summary["unique_chunk_count"],
        "unique_document_count": fp_summary["unique_document_count"],
        "duplicate_chunk_ids": fp_summary["duplicate_chunk_ids"],
        "corpus_versions_found": versions_found,
        "verified": len(errors) == 0,
        "errors": errors,
    }
    return result


def get_alias_target(alias_name, *, qdrant_client: Any = None):
    """Return the collection currently targeted by an alias, if any."""
    active = _active_client(qdrant_client)
    aliases = active.get_aliases()
    for item in aliases.aliases:
        if item.alias_name == alias_name:
            return item.collection_name
    return None


def activate_collection_alias(
    collection_name,
    alias_name,
    expected_points=None,
    *,
    expected_vector_size: Optional[int] = None,
    expected_chunk_set_fingerprint: Optional[str] = None,
    expected_corpus_version: Optional[str] = None,
    expected_embedding_fingerprint: Optional[str] = None,
    release_manifest_path: Optional[str | Path] = None,
    require_verified_eval: bool = False,
    lease_manager: Optional[CorpusLeaseManager] = None,
    qdrant_client: Any = None,
):
    """
    Atomically move the stable runtime alias to a verified physical collection.

    Enforces:
    - Exclusive activation lock (blocked if any active write lease exists on target collection).
    - Optional release manifest quality/build/receipt gate verification.
    - Full collection integrity verification (vector config, count, chunk_set_fingerprint, version).
    - Never deletes the previous alias target so controlled rollback remains possible.
    """
    active = _active_client(qdrant_client)
    if not alias_name or alias_name == collection_name:
        raise ValueError("Alias must be non-empty and differ from collection name")

    manifest: Optional[Dict[str, Any]] = None
    if release_manifest_path is not None:
        manifest = load_release_manifest(release_manifest_path)
        if manifest.get("physical_collection") != collection_name:
            raise ValueError(
                f"Release manifest physical_collection={manifest.get('physical_collection')!r} "
                f"!= target collection {collection_name!r}"
            )
        if manifest.get("serving_alias") != alias_name:
            raise ValueError(
                f"Release manifest serving_alias={manifest.get('serving_alias')!r} "
                f"!= target alias {alias_name!r}"
            )
        blockers = check_release_activation_ready(
            manifest,
            require_verified_eval=require_verified_eval,
        )
        if blockers:
            raise ValueError(
                "Refusing alias activation; release manifest gate failed: "
                + "; ".join(blockers)
            )
        chunk_manifest = manifest.get("chunk_manifest") or {}
        emb_cfg = manifest.get("embedding_config") or {}
        if expected_points is None:
            expected_points = chunk_manifest.get("expected_count")
        if expected_vector_size is None:
            expected_vector_size = emb_cfg.get("vector_size")
        if expected_chunk_set_fingerprint is None:
            expected_chunk_set_fingerprint = chunk_manifest.get("chunk_set_fingerprint")
        if expected_corpus_version is None:
            expected_corpus_version = manifest.get("corpus_version")
        if expected_embedding_fingerprint is None:
            expected_embedding_fingerprint = emb_cfg.get("fingerprint")

    manager = lease_manager or CorpusLeaseManager()
    act_lock = manager.acquire_activation_lock(
        collection_name,
        alias_name,
        release_id=(manifest or {}).get("release_id"),
    )
    try:
        physical_collections = {
            item.name for item in active.get_collections().collections
        }
        if alias_name in physical_collections:
            raise ValueError(
                f"Alias {alias_name!r} conflicts with an existing physical collection. "
                "Choose a separate stable alias, for example 'nmk_chatbot_active'."
            )

        integrity = verify_collection_integrity(
            collection_name,
            expected_points=expected_points,
            expected_vector_size=expected_vector_size,
            expected_chunk_set_fingerprint=expected_chunk_set_fingerprint,
            expected_corpus_version=expected_corpus_version,
            expected_embedding_fingerprint=expected_embedding_fingerprint,
            require_payload_indexes=False,
            qdrant_client=active,
        )
        if not integrity["verified"]:
            raise ValueError(
                "Refusing alias switch; collection integrity check failed: "
                + "; ".join(integrity["errors"])
            )

        ensure_payload_indexes(collection_name, raise_on_error=True, qdrant_client=active)

        current_target = get_alias_target(alias_name, qdrant_client=active)
        operations = []
        if current_target:
            operations.append(
                DeleteAliasOperation(
                    delete_alias=DeleteAlias(alias_name=alias_name),
                )
            )
        operations.append(
            CreateAliasOperation(
                create_alias=CreateAlias(
                    collection_name=collection_name,
                    alias_name=alias_name,
                )
            )
        )

        result = active.update_collection_aliases(
            change_aliases_operations=operations,
        )
        logger.info(
            "Activated Qdrant alias %s: %s -> %s",
            alias_name,
            current_target or "none",
            collection_name,
        )

        if manifest is not None and release_manifest_path is not None:
            manifest["publication_status"] = "published"
            manifest["build_status"] = "verified"
            manifest["previous_release"] = {
                "physical_collection": current_target,
                "switched_at": datetime.now(timezone.utc).isoformat(),
            }
            manifest["verification"] = {
                **(manifest.get("verification") or {}),
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "qdrant_verified": True,
                "count_matched": True,
                "fingerprint_matched": True,
                "payload_indexes_verified": True,
                "errors": [],
            }
            save_release_manifest(release_manifest_path, manifest)

        return {
            "status": bool(result),
            "alias": alias_name,
            "previous_collection": current_target,
            "active_collection": collection_name,
            "points_count": integrity["points_count"],
            "chunk_set_fingerprint": integrity["chunk_set_fingerprint"],
            "release_id": (manifest or {}).get("release_id"),
            "previous_collection_preserved": True,
        }
    finally:
        manager.release_lease(act_lock)


def delete_vectors(
    collection_name,
    point_ids,
    *,
    qdrant_client: Any = None,
    enforce_staging_policy: bool = True,
    protected_aliases: Optional[Iterable[str]] = None,
):
    """
    Xóa các vector khỏi physical staging collection theo danh sách point ID.
    Chặn xóa trực tiếp trên serving alias hoặc physical collection đang phục vụ.
    """
    active = _active_client(qdrant_client)
    if enforce_staging_policy:
        verify_staging_write_target(
            collection_name,
            qdrant_client=active,
            require_corpus_version=False,
            require_allowlist=False,
            protected_aliases=protected_aliases,
            dry_run=False,
        )
    try:
        raw_result = active.delete(
            collection_name=collection_name, points_selector=point_ids, wait=True
        )
        state, detail = interpret_qdrant_upsert_result(raw_result)
        ok = state in {"committed", "unverified_client_return"}
        logger.info(
            "Deleted %s vectors from %s (state=%s)",
            len(point_ids),
            collection_name,
            state,
        )
        return {
            "ok": ok,
            "status": state,
            "detail": detail,
            "attempted_points": len(point_ids),
            "committed_points": len(point_ids) if state == "committed" else 0,
        }
    except Exception as e:
        logger.error(f"Failed to delete vectors: {e}")
        return {
            "ok": False,
            "status": "failed",
            "attempted_points": len(point_ids),
            "committed_points": 0,
            "error": str(e),
        }

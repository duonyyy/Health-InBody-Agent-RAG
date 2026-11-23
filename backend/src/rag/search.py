"""Hybrid search cho Health/InBody Agent RAG với đồng bộ corpus release và request pinning."""
import gzip
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import DEFAULT_COLLECTION_NAME, DEFAULT_QDRANT_SEARCH_TIMEOUT, DEFAULT_VECTOR_SIZE
from harness.budget import (
    BudgetExhaustedError,
    call_with_supported_kwargs,
    remaining_for_call,
    resolve_deadline,
)
from rag.bm25 import (
    HEALTH_DOMAIN_KEYWORDS,
    build_bm25_index as _pure_build_bm25_index,
    compute_bm25_score as _pure_compute_bm25_score,
    detect_content_type as _pure_detect_content_type,
    extract_document_text as _pure_extract_document_text,
    get_bm25_candidate_indices as _pure_get_bm25_candidate_indices,
    is_recipe_document,
    matches_document_filters as _pure_matches_document_filters,
    normalize_lexical_text as _pure_normalize_lexical_text,
    normalize_search_document as _pure_normalize_search_document,
    score_bm25_corpus as _pure_score_bm25_corpus,
    tokenize as _pure_tokenize,
)
from rag.corpus_lifecycle import (
    BM25_TOKENIZER_VERSION,
    CANONICAL_ID_SCHEMA_VERSION,
    CorpusReleaseMismatchError,
    canonical_chunk_identity,
    compute_chunk_set_fingerprint,
    load_release_manifest,
)
from rag.hybrid_fusion import (
    assert_same_chunk_consistency as _pure_assert_same_chunk_consistency,
    canonical_content_key as _pure_canonical_content_key,
    combine_search_results as _pure_combine_search_results,
    expand_parent_documents as _pure_expand_parent_documents,
    normalize_scores as _pure_normalize_scores,
)
from rag.provenance import PROVENANCE_METADATA_FIELDS
from rag.retrieval_errors import RetrievalDependencyError
from rag.query_rewriter import expand_health_query
from rag.rerank import rerank_documents

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "10"))
DEFAULT_DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.6"))
DEFAULT_BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.4"))
ENABLE_PARENT_RETRIEVAL = os.getenv("ENABLE_PARENT_RETRIEVAL", "true").lower() == "true"
BM25_SNAPSHOT_SCHEMA_VERSION = 1
BM25_SNAPSHOT_PATH = os.getenv(
    "BM25_SNAPSHOT_PATH",
    "/usr/src/app/data/generated/bm25_snapshot.json.gz",
)
VALID_MISMATCH_POLICIES = {"refuse", "dense_only", "bm25_only"}

# Process-local lexical index state (owned strictly by a single API process; API_WORKERS=1).
_documents: List[Dict[str, Any]] = []
_bm25_index: Dict[str, Any] = {}
_search_engine_initialized = False
_search_index_metadata: Dict[str, Any] = {}

HEALTH_DOMAIN_KEYWORDS = {
    "inbody_metric": [
        "inbody",
        "bmi",
        "smm",
        "bfm",
        "pbf",
        "visceral fat",
        "mỡ nội tạng",
        "khối lượng cơ",
        "khối lượng mỡ",
    ],
    "nutrition": [
        "dinh dưỡng",
        "ăn uống",
        "calo",
        "calorie",
        "protein",
        "carb",
        "chất béo",
        "khẩu phần",
    ],
    "exercise": [
        "tập luyện",
        "lịch tập",
        "cardio",
        "kháng lực",
        "tăng cơ",
        "giảm mỡ",
        "phục hồi",
    ],
    "medical_safety": [
        "bác sĩ",
        "triệu chứng",
        "bệnh nền",
        "thuốc",
        "chẩn đoán",
        "cấp cứu",
        "an toàn",
    ],
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _retrieval_mismatch_policy(explicit: Optional[str] = None) -> str:
    raw = str(
        explicit if explicit is not None else os.getenv("RETRIEVAL_MISMATCH_POLICY", "refuse")
    ).strip().lower()
    if raw not in VALID_MISMATCH_POLICIES:
        return "refuse"
    return raw


def validate_lexical_worker_config() -> Dict[str, Any]:
    """Block unsupported multi-worker configurations while BM25 lives in process-local RAM."""
    raw_workers = str(os.getenv("API_WORKERS", "1")).strip()
    try:
        workers = int(raw_workers) if raw_workers else 1
    except ValueError:
        workers = 1
    bm25_autoload = os.getenv("BM25_AUTOLOAD", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    allow_override = os.getenv("ALLOW_UNSUPPORTED_MULTI_WORKER_BM25", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if workers > 1 and bm25_autoload and not allow_override:
        raise RuntimeError(
            f"Cấu hình API_WORKERS={workers} không được hỗ trợ khi BM25 chạy in-memory trong từng process "
            "(mỗi worker sẽ giữ bản sao RAM riêng và không đồng bộ khi phát hành corpus). "
            "Giữ API_WORKERS=1 hoặc tắt BM25_AUTOLOAD."
        )
    return {
        "lexical_index_owner": "single_api_process_in_memory",
        "multi_worker_supported": False,
        "configured_api_workers": workers,
        "bm25_autoload": bm25_autoload,
    }


def _resolve_alias_target(alias_name: str, qdrant_client: Any = None) -> Optional[str]:
    """Resolve current physical collection pointed to by a Qdrant alias, if available."""
    try:
        from rag.qdrant.client import get_alias_target

        return get_alias_target(alias_name, qdrant_client=qdrant_client)
    except Exception as exc:
        logger.debug("Could not resolve Qdrant alias %s (%s)", alias_name, type(exc).__name__)
        return None


def _normalize_lexical_text(text: str) -> str:
    """Normalize Vietnamese accents so legacy ASCII documents remain searchable."""
    return _pure_normalize_lexical_text(text)


def _tokenize(text: str) -> List[str]:
    return _pure_tokenize(text)


def _document_text(doc: Dict[str, Any]) -> str:
    return _pure_extract_document_text(doc)


def _detect_content_type(text: str) -> str:
    return _pure_detect_content_type(text, domain_keywords=HEALTH_DOMAIN_KEYWORDS)


def _normalize_document(doc: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    return _pure_normalize_search_document(doc, index)


def _build_bm25_index(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _pure_build_bm25_index(documents)


def _bm25_score(query_tokens: List[str], doc_index: int, k1: float = 1.5, b: float = 0.75):
    return _pure_compute_bm25_score(query_tokens, doc_index, _bm25_index, k1=k1, b=b)


def _normalize_scores(scored_docs: List[Tuple[int, float]]) -> Dict[int, float]:
    return _pure_normalize_scores(scored_docs)


def initialize_search_index(
    documents: List[Dict],
    snapshot_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Khoi tao BM25 index tu kho tai lieu suc khoe/InBody."""
    global _documents, _bm25_index, _search_engine_initialized, _search_index_metadata

    try:
        normalized_docs = []
        for index, doc in enumerate(documents or []):
            normalized = _normalize_document(doc, index)
            if normalized:
                normalized_docs.append(normalized)

        if not normalized_docs:
            logger.warning("No valid Health/InBody documents for search indexing")
            _documents = []
            _bm25_index = {}
            _search_engine_initialized = False
            _search_index_metadata = {}
            return False

        fp_info = compute_chunk_set_fingerprint(normalized_docs)
        _documents = normalized_docs
        _bm25_index = _build_bm25_index(_documents)
        _search_engine_initialized = True
        _search_index_metadata = {
            **dict(snapshot_metadata or {}),
            "chunk_set_fingerprint": (snapshot_metadata or {}).get("chunk_set_fingerprint")
            or fp_info["chunk_set_fingerprint"],
            "unique_chunk_count": fp_info["unique_chunk_count"],
            "unique_document_count": fp_info["unique_document_count"],
            "tokenizer_version": BM25_TOKENIZER_VERSION,
            "canonical_id_schema": CANONICAL_ID_SCHEMA_VERSION,
            "snapshot_error": None,
        }

        logger.info(
            "Initialized Health/InBody BM25 index with %s documents (fp=%s)",
            len(_documents),
            _search_index_metadata["chunk_set_fingerprint"][:16],
        )
        return True
    except Exception as e:
        logger.error("Failed to initialize Health/InBody search index: %s", e)
        _search_engine_initialized = False
        _search_index_metadata = {"snapshot_error": str(e)}
        return False


def save_search_snapshot(
    snapshot_path: str | Path | None = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist normalized BM25 documents atomically (temp + fsync + replace) with fingerprint."""
    global _search_index_metadata
    if not _search_engine_initialized or not _documents:
        logger.warning("Cannot persist BM25 snapshot before index initialization")
        return False

    path = Path(snapshot_path or BM25_SNAPSHOT_PATH)
    created_at = datetime.now(timezone.utc).isoformat()
    fp_info = compute_chunk_set_fingerprint(_documents)
    merged_meta = {
        **dict(metadata or {}),
        "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
        "unique_chunk_count": fp_info["unique_chunk_count"],
        "unique_document_count": fp_info["unique_document_count"],
        "tokenizer_version": BM25_TOKENIZER_VERSION,
        "canonical_id_schema": CANONICAL_ID_SCHEMA_VERSION,
    }
    physical_collection = merged_meta.get("physical_collection")
    release_id = merged_meta.get("release_id")
    corpus_version = merged_meta.get("corpus_version")

    payload = {
        "schema_version": BM25_SNAPSHOT_SCHEMA_VERSION,
        "collection_name": DEFAULT_COLLECTION_NAME,
        "physical_collection": physical_collection,
        "release_id": release_id,
        "corpus_version": corpus_version,
        "created_at": created_at,
        "document_count": len(_documents),
        "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
        "metadata": merged_meta,
        "documents": _documents,
    }

    temporary_path: Optional[Path] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(tmp_name)
        with os.fdopen(fd, "wb") as raw_handle:
            with gzip.GzipFile(fileobj=raw_handle, mode="wb") as gz_handle:
                gz_handle.write(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                )
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        os.replace(temporary_path, path)
        snapshot_sha = _sha256_file(path)
        _search_index_metadata = {
            **_search_index_metadata,
            **merged_meta,
            "snapshot_persisted": True,
            "snapshot_path": str(path),
            "snapshot_sha256": snapshot_sha,
            "snapshot_created_at": created_at,
            "snapshot_error": None,
        }
        logger.info(
            "Persisted BM25 snapshot with %s documents (fp=%s)",
            len(_documents),
            fp_info["chunk_set_fingerprint"][:16],
        )
        return True
    except Exception as exc:
        logger.error("Failed to persist BM25 snapshot: %s", exc)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except Exception:
                pass
        return False


def load_search_snapshot(
    snapshot_path: str | Path | None = None,
    *,
    expected_physical_collection: Optional[str] = None,
    expected_corpus_version: Optional[str] = None,
    expected_release_id: Optional[str] = None,
    expected_chunk_set_fingerprint: Optional[str] = None,
    qdrant_client: Any = None,
    verify_against_qdrant: bool = False,
) -> bool:
    """Load a verified local JSON-gzip snapshot and rebuild the in-memory BM25 index.

    Rejects corrupt/partial files, mismatched fingerprints (even when count matches),
    or mismatched physical release targets.
    """
    global _documents, _bm25_index, _search_engine_initialized, _search_index_metadata

    path = Path(snapshot_path or BM25_SNAPSHOT_PATH)
    if not path.exists():
        logger.warning("BM25 snapshot is not available at configured path")
        _search_engine_initialized = False
        _search_index_metadata = {
            "snapshot_loaded": False,
            "snapshot_path": str(path),
            "snapshot_error": "snapshot_not_found",
            "release_sync_status": "uninitialized",
        }
        return False

    try:
        snapshot_sha = _sha256_file(path)
        with gzip.open(path, "rt", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise ValueError("BM25 snapshot root payload is not a JSON object")
        if payload.get("schema_version") != BM25_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported BM25 snapshot schema")
        if payload.get("collection_name") != DEFAULT_COLLECTION_NAME:
            raise ValueError("BM25 snapshot collection does not match runtime collection")
        documents = payload.get("documents")
        if not isinstance(documents, list):
            raise ValueError("BM25 snapshot documents field is invalid")
        if int(payload.get("document_count") or 0) != len(documents):
            raise ValueError("BM25 snapshot document count is inconsistent")

        header_meta = dict(payload.get("metadata") or {})
        declared_fp = str(
            payload.get("chunk_set_fingerprint")
            or header_meta.get("chunk_set_fingerprint")
            or ""
        ).strip()
        computed_fp_info = compute_chunk_set_fingerprint(documents)
        computed_fp = computed_fp_info["chunk_set_fingerprint"]
        if declared_fp and declared_fp != computed_fp:
            raise ValueError(
                f"BM25 snapshot chunk_set_fingerprint mismatch "
                f"(declared={declared_fp[:16]} != computed={computed_fp[:16]})"
            )
        if expected_chunk_set_fingerprint and computed_fp != expected_chunk_set_fingerprint:
            raise ValueError(
                f"BM25 snapshot chunk_set_fingerprint does not match expected release "
                f"({computed_fp[:16]} != {expected_chunk_set_fingerprint[:16]})"
            )

        snap_version = str(
            payload.get("corpus_version") or header_meta.get("corpus_version") or ""
        ).strip() or None
        snap_release_id = str(
            payload.get("release_id") or header_meta.get("release_id") or ""
        ).strip() or None
        snap_physical = str(
            payload.get("physical_collection") or header_meta.get("physical_collection") or ""
        ).strip() or None

        if expected_corpus_version and snap_version != expected_corpus_version:
            raise ValueError(
                f"BM25 snapshot corpus_version={snap_version!r} != expected {expected_corpus_version!r}"
            )
        if expected_release_id and snap_release_id != expected_release_id:
            raise ValueError(
                f"BM25 snapshot release_id={snap_release_id!r} != expected {expected_release_id!r}"
            )
        if expected_physical_collection and snap_physical != expected_physical_collection:
            raise ValueError(
                f"BM25 snapshot physical_collection={snap_physical!r} != expected {expected_physical_collection!r}"
            )

        sync_status = "unverified"
        if verify_against_qdrant:
            live_physical = _resolve_alias_target(DEFAULT_COLLECTION_NAME, qdrant_client=qdrant_client)
            if not live_physical:
                raise ValueError("Could not resolve live Qdrant alias target for BM25 verification")
            if not snap_physical or snap_physical != live_physical:
                raise ValueError(
                    f"BM25 snapshot physical_collection={snap_physical!r} does not match live "
                    f"Qdrant alias target {live_physical!r}"
                )
            sync_status = "synced"

        metadata = {
            **header_meta,
            "corpus_version": snap_version,
            "release_id": snap_release_id,
            "physical_collection": snap_physical,
            "chunk_set_fingerprint": computed_fp,
            "snapshot_sha256": snapshot_sha,
            "snapshot_loaded": True,
            "snapshot_path": str(path),
            "snapshot_created_at": payload.get("created_at"),
            "release_sync_status": sync_status,
            "release_mismatch_reason": None,
        }
        return initialize_search_index(documents, snapshot_metadata=metadata)
    except Exception as exc:
        logger.error("Failed to load BM25 snapshot: %s", exc)
        _documents = []
        _bm25_index = {}
        _search_engine_initialized = False
        _search_index_metadata = {
            "snapshot_loaded": False,
            "snapshot_path": str(path),
            "snapshot_error": str(exc),
            "release_sync_status": "mismatch",
            "release_mismatch_reason": str(exc),
        }
        return False


def verify_runtime_release_sync(
    *,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    qdrant_client: Any = None,
    release_manifest_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Verify consistency between live Qdrant alias target, loaded BM25 snapshot, and release manifest."""
    live_physical = _resolve_alias_target(collection_name, qdrant_client=qdrant_client)
    bm25_physical = _search_index_metadata.get("physical_collection")
    bm25_release_id = _search_index_metadata.get("release_id")
    bm25_version = _search_index_metadata.get("corpus_version")
    bm25_fp = _search_index_metadata.get("chunk_set_fingerprint")

    manifest_path = release_manifest_path or os.getenv("CORPUS_RELEASE_MANIFEST_PATH") or None
    require_manifest = (
        os.getenv("CORPUS_REQUIRE_MANIFEST", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    manifest: Optional[Dict[str, Any]] = None
    manifest_error: Optional[str] = None
    if manifest_path:
        try:
            manifest = load_release_manifest(manifest_path)
        except Exception as exc:
            manifest_error = str(exc)
    elif require_manifest:
        manifest_error = "Manifest bắt buộc nhưng CORPUS_RELEASE_MANIFEST_PATH không được cấu hình"

    reasons: List[str] = []
    if manifest_error:
        reasons.append(f"Release manifest invalid/unreadable: {manifest_error}")

    if _search_index_metadata.get("snapshot_error"):
        reasons.append(f"BM25 snapshot error: {_search_index_metadata['snapshot_error']}")

    if live_physical and _search_engine_initialized:
        if bm25_physical and bm25_physical != live_physical:
            reasons.append(
                f"BM25 physical_collection={bm25_physical!r} != Qdrant alias {collection_name!r} -> {live_physical!r}"
            )
        elif not bm25_physical and manifest is not None:
            reasons.append("BM25 snapshot lacks physical_collection binding")

    if manifest is not None:
        m_phys = manifest.get("physical_collection")
        m_ver = manifest.get("corpus_version")
        m_rel = manifest.get("release_id")
        m_fp = (manifest.get("chunk_manifest") or {}).get("chunk_set_fingerprint")
        if live_physical and m_phys != live_physical:
            reasons.append(
                f"Live alias target {live_physical!r} != release manifest physical_collection={m_phys!r}"
            )
        if _search_engine_initialized:
            artifact = manifest.get("bm25_artifact") or {}
            expected_snapshot_sha = artifact.get("sha256")
            loaded_snapshot_sha = _search_index_metadata.get("snapshot_sha256")
            if not expected_snapshot_sha or loaded_snapshot_sha != expected_snapshot_sha:
                reasons.append("BM25 snapshot sha256 thiếu hoặc không khớp release manifest")
            if m_ver and bm25_version != m_ver:
                reasons.append(f"BM25 corpus_version={bm25_version!r} != manifest {m_ver!r}")
            if m_rel and bm25_release_id != m_rel:
                reasons.append(f"BM25 release_id={bm25_release_id!r} != manifest {m_rel!r}")
            if m_fp and bm25_fp != m_fp:
                reasons.append(
                    f"BM25 chunk_set_fingerprint={(bm25_fp or '')[:16]} != manifest {(m_fp or '')[:16]}"
                )

    if reasons:
        status = "mismatch"
    elif live_physical and bm25_physical and live_physical == bm25_physical:
        status = "synced"
    elif _search_engine_initialized:
        status = "unverified"
    else:
        status = "uninitialized"

    synced = status == "synced"
    if not synced and not reasons:
        reasons.append("Không thể xác minh BM25 và alias Qdrant cùng collection vật lý")

    _search_index_metadata["release_sync_status"] = status
    _search_index_metadata["release_mismatch_reason"] = "; ".join(reasons) if reasons else None
    if live_physical:
        _search_index_metadata["last_pinned_physical_collection"] = live_physical

    return {
        "synced": synced,
        "status": status,
        "alias_name": collection_name,
        "live_physical_collection": live_physical,
        "pinned_collection": live_physical or collection_name,
        "bm25_physical_collection": bm25_physical,
        "bm25_release_id": bm25_release_id,
        "bm25_corpus_version": bm25_version,
        "bm25_chunk_set_fingerprint": bm25_fp,
        "reasons": reasons,
    }


def _bm25_candidate_indices(filters: Optional[Dict[str, Any]]) -> List[int] | range:
    """Narrow the common content-type filter before scoring the BM25 corpus."""
    return _pure_get_bm25_candidate_indices(len(_documents), _bm25_index, filters)


def bm25_search(
    query: str,
    limit: int = DEFAULT_TOP_K,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Tim kiem keyword BM25 trong in-memory Health/InBody index."""
    if not _search_engine_initialized or not _documents:
        return []

    query_tokens = _tokenize(query)
    scored_docs = []

    for index in _bm25_candidate_indices(filters):
        doc = _documents[index]
        if not _matches_filters(doc, filters):
            continue
        score = _bm25_score(query_tokens, index)
        if score <= 0:
            continue

        result = doc.copy()
        result["bm25_score"] = score
        result["search_method"] = "bm25"
        result["retrieval_mode"] = "bm25_only"
        scored_docs.append((result, score))

    scored_docs.sort(key=lambda item: item[1], reverse=True)
    return [doc for doc, _ in scored_docs[:limit]]


def _get_embedding(
    query: str,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    raise_on_timeout: bool = False,
):
    try:
        from llm.client import get_embedding

        return call_with_supported_kwargs(
            get_embedding,
            query,
            input_type="query",
            timeout=timeout,
            deadline_monotonic=deadline_monotonic,
        )
    except Exception as e:
        is_timeout = isinstance(e, (BudgetExhaustedError, TimeoutError)) or "timeout" in type(e).__name__.lower()
        logger.warning("Embedding is not available (%s)", type(e).__name__)
        if is_timeout:
            raise BudgetExhaustedError("Embedding timed out") from e
        raise RetrievalDependencyError("embedding_unavailable") from e


def vector_search_fallback(
    query: str,
    limit: int = DEFAULT_TOP_K,
    filters: Optional[Dict[str, Any]] = None,
    embedding_timeout: Optional[float] = None,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    raise_on_timeout: bool = False,
    *,
    collection_name: Optional[str] = None,
    qdrant_client: Any = None,
) -> List[Dict]:
    """Tim kiem vector trong Qdrant tren chinh xac collection da pin cho request."""
    target_collection = collection_name or DEFAULT_COLLECTION_NAME
    effective_deadline = None
    if deadline_monotonic is not None or timeout is not None:
        effective_deadline = resolve_deadline(
            timeout=timeout,
            deadline_monotonic=deadline_monotonic,
            default_timeout=max(float(DEFAULT_QDRANT_SEARCH_TIMEOUT), float(embedding_timeout or 15.0)),
        )

    effective_embed_timeout = remaining_for_call(
        effective_deadline,
        embedding_timeout,
        default_timeout=15.0,
    )
    if effective_deadline is not None and effective_embed_timeout is None:
        raise BudgetExhaustedError("Vector search budget exhausted before embedding")

    vector = _get_embedding(
        query,
        timeout=effective_embed_timeout,
        deadline_monotonic=effective_deadline,
        raise_on_timeout=raise_on_timeout,
    )
    if vector is None:
        raise RetrievalDependencyError("embedding_unavailable")
    if (not isinstance(vector, (list, tuple)) or not vector
            or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector)):
        raise RetrievalDependencyError("invalid_embedding")

    expected_dimension = DEFAULT_VECTOR_SIZE
    if qdrant_client is not None:
        try:
            expected_dimension = qdrant_client.get_collection(target_collection).config.params.vectors.size
        except Exception as exc:
            raise RetrievalDependencyError("qdrant_unavailable") from exc
    if len(vector) != expected_dimension:
        raise RetrievalDependencyError("invalid_embedding")

    qdrant_timeout = remaining_for_call(
        effective_deadline,
        DEFAULT_QDRANT_SEARCH_TIMEOUT,
        default_timeout=DEFAULT_QDRANT_SEARCH_TIMEOUT,
        min_timeout=1.0,
    )
    if effective_deadline is not None and qdrant_timeout is None:
        raise BudgetExhaustedError("Vector search budget exhausted before Qdrant query")

    try:
        from rag.qdrant.client import search_vector

        results = call_with_supported_kwargs(
            search_vector,
            target_collection,
            vector,
            limit=limit,
            filters=filters,
            timeout=qdrant_timeout,
            deadline_monotonic=effective_deadline,
            raise_on_timeout=raise_on_timeout,
            raise_on_error=True,
            qdrant_client=qdrant_client,
        )
    except BudgetExhaustedError:
        raise
    except RetrievalDependencyError:
        raise
    except Exception as e:
        logger.error("Vector search failed (%s)", type(e).__name__)
        raise RetrievalDependencyError("qdrant_unavailable") from e

    for result in results:
        result["search_method"] = "vector"
        result["retrieval_mode"] = "dense_only"
        result["active_physical_collection"] = target_collection
        result["vector_score"] = result.get("similarity_score", 0)
        result["hybrid_score"] = result.get("similarity_score", 0)
        result.setdefault("domain", "health_inbody")
        result.setdefault(
            "content_type",
            _detect_content_type(_document_text(result)),
        )

    return results[:limit]


def _content_key(doc: Dict[str, Any]) -> tuple:
    return _pure_canonical_content_key(doc)


def _check_same_chunk(first: Dict[str, Any], second: Dict[str, Any]) -> None:
    _pure_assert_same_chunk_consistency(first, second)


def _matches_filters(doc: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """Apply simple equality/range filters to non-Qdrant retrieval results."""
    return _pure_matches_document_filters(doc, filters)


def combine_search_results(
    bm25_results,
    vector_results,
    query: str,
    dense_weight: float = DEFAULT_DENSE_WEIGHT,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
) -> List[Dict]:
    """Gop ket qua BM25 va vector search thanh danh sach co hybrid_score trung thuc."""
    return _pure_combine_search_results(
        bm25_results,
        vector_results,
        query,
        dense_weight=dense_weight,
        bm25_weight=bm25_weight,
        domain_keywords=HEALTH_DOMAIN_KEYWORDS,
    )


def expand_parent_documents(
    docs: List[Dict[str, Any]],
    max_parents: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Expand retrieved child chunks to their parent documents while deduplicating by parent_id."""
    return _pure_expand_parent_documents(docs, max_parents=max_parents)


def hybrid_search(
    query: str,
    limit: int = DEFAULT_TOP_K,
    filters: Optional[Dict[str, Any]] = None,
    use_rerank: bool = True,
    embedding_timeout: Optional[float] = None,
    expand_parents: Optional[bool] = None,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    raise_on_timeout: bool = False,
    *,
    qdrant_client: Any = None,
    mismatch_policy: Optional[str] = None,
    release_manifest_path: Optional[str | Path] = None,
    request_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """
    Tim kiem hybrid cho Health/InBody RAG voi release consistency & request pinning.

    1. Pin physical collection tai dau request (khong tron 2 release neu alias doi giua request).
    2. Doi chieu BM25 snapshot voi live Qdrant physical release & manifest.
    3. Neu mismatch: khong am tham chay hybrid; xu ly theo RETRIEVAL_MISMATCH_POLICY
       (`refuse` mac dinh, hoac `dense_only` / `bm25_only` tuong minh co gan nhan trung thuc).
    4. Khong goi ket qua la `hybrid` neu chi mot nhanh tham gia.
    """
    if not query or not query.strip():
        return []

    effective_deadline = None
    if deadline_monotonic is not None or timeout is not None:
        effective_deadline = resolve_deadline(
            timeout=timeout,
            deadline_monotonic=deadline_monotonic,
            default_timeout=15.0,
        )
        if remaining_for_call(effective_deadline, timeout, default_timeout=15.0) is None:
            raise BudgetExhaustedError("Hybrid search budget exhausted")

    # Pin physical collection & check release sync at request start.
    should_check_sync = bool(
        request_context is not None
        or qdrant_client is not None
        or _search_index_metadata.get("physical_collection")
        or release_manifest_path is not None
        or os.getenv("CORPUS_RELEASE_MANIFEST_PATH")
        or os.getenv("CORPUS_VERIFY_ALIAS_ON_SEARCH", "false").strip().lower() in {"1", "true", "yes", "on"}
    )
    pinned_collection = DEFAULT_COLLECTION_NAME
    allow_bm25 = True
    allow_dense = True
    release_mismatch_degraded = False
    active_release_id = _search_index_metadata.get("release_id")
    active_corpus_version = _search_index_metadata.get("corpus_version")

    if should_check_sync:
        sync_info = verify_runtime_release_sync(
            collection_name=DEFAULT_COLLECTION_NAME,
            qdrant_client=qdrant_client,
            release_manifest_path=release_manifest_path,
        )
        pinned_collection = sync_info["pinned_collection"]
        if not sync_info["synced"]:
            policy = _retrieval_mismatch_policy(mismatch_policy)
            reason = "; ".join(sync_info["reasons"])
            logger.error(
                "Corpus release mismatch detected (policy=%s): %s",
                policy,
                reason,
            )
            if policy == "refuse":
                raise CorpusReleaseMismatchError(
                    f"Không thể chạy hybrid search do lệch phiên bản corpus giữa Qdrant và BM25: {reason}"
                )
            elif policy == "dense_only":
                allow_bm25 = False
                allow_dense = True
                release_mismatch_degraded = True
                active_release_id = None
            elif policy == "bm25_only":
                allow_bm25 = True
                allow_dense = False
                release_mismatch_degraded = True
                pinned_collection = sync_info["bm25_physical_collection"] or DEFAULT_COLLECTION_NAME

    # Shared by every subquery, including successful zero-hit queries. Refuse
    # before retrieval if the physical release or lexical snapshot has changed.
    release_pin = (pinned_collection, active_release_id, active_corpus_version,
                   _search_index_metadata.get("chunk_set_fingerprint"), allow_bm25, allow_dense)
    if request_context is not None:
        if "release_pin" in request_context and request_context["release_pin"] != release_pin:
            raise CorpusReleaseMismatchError("Corpus changed between retrieval queries")
        request_context["release_pin"] = release_pin

    should_expand = ENABLE_PARENT_RETRIEVAL if expand_parents is None else expand_parents
    candidate_limit = limit * 3 if should_expand else limit * 2

    bm25_results: List[Dict[str, Any]] = []
    if allow_bm25:
        bm25_results = bm25_search(query, limit=candidate_limit, filters=filters)

    candidate_count = len(_bm25_candidate_indices(filters)) if allow_bm25 else 0
    bm25_covers_filtered_corpus = bool(
        allow_bm25
        and filters
        and candidate_count
        and candidate_count <= candidate_limit
        and len(bm25_results) >= candidate_count
    )

    vector_results: List[Dict[str, Any]] = []
    if allow_dense and not bm25_covers_filtered_corpus:
        vector_results = call_with_supported_kwargs(
            vector_search_fallback,
            query,
            limit=candidate_limit,
            filters=filters,
            embedding_timeout=embedding_timeout,
            timeout=timeout,
            deadline_monotonic=effective_deadline,
            raise_on_timeout=raise_on_timeout,
            collection_name=pinned_collection,
            qdrant_client=qdrant_client,
        )
    elif bm25_covers_filtered_corpus:
        logger.info(
            "BM25 covered all %s filtered candidates; skipped redundant vector search",
            candidate_count,
        )

    bm25_results = [doc for doc in bm25_results if _matches_filters(doc, filters)]
    vector_results = [doc for doc in vector_results if _matches_filters(doc, filters)]

    if bm25_results or vector_results:
        combined = combine_search_results(bm25_results, vector_results, query)
        actual_mode = (
            "hybrid"
            if (bm25_results and vector_results)
            else ("bm25_only" if bm25_results else "dense_only")
        )
        for doc in combined:
            doc["retrieval_mode"] = actual_mode
            doc["active_physical_collection"] = pinned_collection
            if active_release_id and not doc.get("release_id"):
                doc["release_id"] = active_release_id
            if active_corpus_version and not doc.get("corpus_version") and not release_mismatch_degraded:
                doc["corpus_version"] = active_corpus_version
            if release_mismatch_degraded:
                doc["release_mismatch_degraded"] = True
    else:
        if release_mismatch_degraded:
            raise CorpusReleaseMismatchError("Corpus release mismatch; fallback returned no results")
        logger.info("No BM25/vector results available")
        combined = []

    if use_rerank and combined:
        rerank_pool = combined[:candidate_limit]
        reranked = call_with_supported_kwargs(
            rerank_documents,
            rerank_pool,
            query,
            top_n=candidate_limit,
            deadline_monotonic=effective_deadline,
        )
        if should_expand:
            return expand_parent_documents(reranked, max_parents=limit)
        return reranked[:limit]

    if should_expand:
        return expand_parent_documents(combined, max_parents=limit)

    return combined[:limit]


def search_engine() -> bool:
    """Alias tuong thich voi prototype cu."""
    return _search_engine_initialized


def get_search_stats() -> Dict:
    """Lay thong tin trang thai search index va corpus release."""
    raw_workers = str(os.getenv("API_WORKERS", "1")).strip()
    try:
        workers = int(raw_workers) if raw_workers else 1
    except ValueError:
        workers = 1
    return {
        "initialized": _search_engine_initialized,
        "documents_count": len(_documents),
        "has_bm25": bool(_bm25_index),
        "bm25_persistence": (
            "versioned_json_gzip_snapshot"
            if _search_index_metadata.get("snapshot_loaded")
            or _search_index_metadata.get("snapshot_persisted")
            else "process_local_nonpersistent"
        ),
        "lexical_index_owner": "single_api_process_in_memory",
        "multi_worker_supported": False,
        "configured_api_workers": workers,
        "snapshot_created_at": _search_index_metadata.get("snapshot_created_at"),
        "snapshot_sha256": _search_index_metadata.get("snapshot_sha256"),
        "snapshot_point_count": _search_index_metadata.get("qdrant_point_count"),
        "snapshot_error": _search_index_metadata.get("snapshot_error"),
        "corpus_version": _search_index_metadata.get("corpus_version"),
        "release_id": _search_index_metadata.get("release_id"),
        "physical_collection": _search_index_metadata.get("physical_collection"),
        "chunk_set_fingerprint": _search_index_metadata.get("chunk_set_fingerprint"),
        "tokenizer_version": _search_index_metadata.get("tokenizer_version") or BM25_TOKENIZER_VERSION,
        "release_sync_status": _search_index_metadata.get("release_sync_status")
        or ("uninitialized" if not _search_engine_initialized else "unverified"),
        "release_mismatch_reason": _search_index_metadata.get("release_mismatch_reason"),
        "retrieval_mismatch_policy": _retrieval_mismatch_policy(),
        "collection_name": DEFAULT_COLLECTION_NAME,
        "domain": "health_inbody",
    }


def force_initialize_if_needed() -> bool:
    if _search_engine_initialized:
        return True
    return initialize_from_vector_store()


def initialize_from_vector_store(
    limit: int = 1000,
    vector_client: Any = None,
    persist_snapshot: bool = False,
    snapshot_path: str | Path | None = None,
    *,
    collection_name: Optional[str] = None,
    corpus_version: Optional[str] = None,
    release_id: Optional[str] = None,
) -> bool:
    """Load payload tu Qdrant de khoi tao BM25 index va (tuy chon) luu snapshot gan release."""
    target_collection = collection_name or DEFAULT_COLLECTION_NAME
    try:
        if vector_client is None:
            from rag.qdrant.client import client as vector_client

        physical_collection = _resolve_alias_target(target_collection, qdrant_client=vector_client)
        effective_scroll_collection = physical_collection or target_collection

        points = []
        next_offset = None
        while True:
            page, next_offset = vector_client.scroll(
                collection_name=effective_scroll_collection,
                limit=limit,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            points.extend(page or [])
            if next_offset is None or not page:
                break
    except Exception as e:
        logger.warning("Could not initialize search index from vector store: %s", e)
        return False

    documents = []
    for index, point in enumerate(points or []):
        payload = dict(point.payload or {})
        doc_id = payload.get("doc_id", point.id if point else index)
        document_id = payload.get("document_id") or doc_id
        chunk_id = payload.get("chunk_id") or doc_id
        documents.append(
            {
                **payload,
                "question": payload.get("question", ""),
                "title": payload.get("title") or payload.get("question", ""),
                "content": payload.get("content", ""),
                "source": payload.get("source", "vector_store"),
                "doc_id": doc_id,
                "document_id": document_id,
                "chunk_id": chunk_id,
                "qdrant_point_id": str(point.id) if getattr(point, "id", None) is not None else payload.get("qdrant_point_id"),
                "content_type": payload.get("content_type"),
                "domain": payload.get("domain", "health_inbody"),
            }
        )

    inferred_version = corpus_version or next(
        (
            str((point.payload or {}).get("corpus_version"))
            for point in points
            if (point.payload or {}).get("corpus_version")
        ),
        None,
    )
    inferred_release_id = release_id or next(
        (
            str((point.payload or {}).get("release_id"))
            for point in points
            if (point.payload or {}).get("release_id")
        ),
        None,
    )
    metadata = {
        "qdrant_point_count": len(points),
        "corpus_version": inferred_version,
        "release_id": inferred_release_id,
        "physical_collection": physical_collection or (collection_name if collection_name != DEFAULT_COLLECTION_NAME else None),
    }
    initialized = initialize_search_index(documents, snapshot_metadata=metadata)
    if initialized and persist_snapshot:
        if not save_search_snapshot(snapshot_path=snapshot_path, metadata=metadata):
            return False
    return initialized

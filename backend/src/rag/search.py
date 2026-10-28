"""Hybrid search cho Health/InBody Agent RAG."""
import gzip
import json
import logging
import math
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import DEFAULT_COLLECTION_NAME
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


def _normalize_lexical_text(text: str) -> str:
    """Normalize Vietnamese accents so legacy ASCII documents remain searchable."""
    lowered = (text or "").lower().replace("đ", "d")
    return "".join(
        character
        for character in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(character) != "Mn"
    )


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", _normalize_lexical_text(text))


def _document_text(doc: Dict[str, Any]) -> str:
    title = doc.get("title", "") or doc.get("question", "") or ""
    content = doc.get("content", "") or doc.get("page_content", "") or ""
    source = doc.get("source", "") or doc.get("source_file", "") or ""
    return f"{title}\n{content}\n{source}".strip()


def _detect_content_type(text: str) -> str:
    text_lower = (text or "").lower()
    for content_type, keywords in HEALTH_DOMAIN_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            return content_type
    return "general_health"


def _normalize_document(doc: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    text = _document_text(doc)
    if not text:
        return None

    normalized = {
        "title": doc.get("title", "") or doc.get("question", ""),
        "question": doc.get("question", ""),
        "content": doc.get("content", "") or doc.get("page_content", ""),
        "source": doc.get("source", "") or doc.get("source_file", "unknown"),
        "doc_id": str(doc.get("doc_id", doc.get("id", index))),
        "content_type": doc.get("content_type") or _detect_content_type(text),
        "domain": doc.get("domain", "health_inbody"),
    }

    for key, value in doc.items():
        normalized.setdefault(key, value)

    return normalized


def _build_bm25_index(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    tokenized_docs = [_tokenize(_document_text(doc)) for doc in documents]
    doc_freq = Counter()
    content_type_indices: Dict[str, List[int]] = {}

    for index, tokens in enumerate(tokenized_docs):
        doc_freq.update(set(tokens))
        content_type = documents[index].get("content_type")
        if content_type:
            content_type_indices.setdefault(str(content_type), []).append(index)

    doc_count = len(tokenized_docs)
    avg_doc_len = (
        sum(len(tokens) for tokens in tokenized_docs) / doc_count if doc_count else 0
    )

    return {
        "tokenized_docs": tokenized_docs,
        "doc_freq": doc_freq,
        "doc_count": doc_count,
        "avg_doc_len": avg_doc_len,
        "content_type_indices": content_type_indices,
    }


def _bm25_score(query_tokens: List[str], doc_index: int, k1: float = 1.5, b: float = 0.75):
    tokenized_docs = _bm25_index.get("tokenized_docs", [])
    if doc_index >= len(tokenized_docs):
        return 0.0

    doc_tokens = tokenized_docs[doc_index]
    if not doc_tokens:
        return 0.0

    term_freq = Counter(doc_tokens)
    doc_freq = _bm25_index.get("doc_freq", Counter())
    doc_count = _bm25_index.get("doc_count", 0)
    avg_doc_len = _bm25_index.get("avg_doc_len", 0) or 1
    doc_len = len(doc_tokens)

    score = 0.0
    for token in query_tokens:
        if token not in term_freq:
            continue

        df = doc_freq.get(token, 0)
        idf = math.log(1 + ((doc_count - df + 0.5) / (df + 0.5)))
        numerator = term_freq[token] * (k1 + 1)
        denominator = term_freq[token] + k1 * (1 - b + b * (doc_len / avg_doc_len))
        score += idf * (numerator / denominator)

    return score


def _normalize_scores(scored_docs: List[Tuple[int, float]]) -> Dict[int, float]:
    if not scored_docs:
        return {}

    max_score = max(score for _, score in scored_docs) or 1.0
    return {idx: score / max_score for idx, score in scored_docs}


def initialize_search_index(
    documents: List[Dict],
    snapshot_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Khoi tao BM25 index tu kho tai lieu suc khoe/InBody.

    Args:
        documents: Danh sach document co cac field nhu question, content,
            source, doc_id, content_type.

    Returns:
        True neu index duoc tao thanh cong.
    """
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

        _documents = normalized_docs
        _bm25_index = _build_bm25_index(_documents)
        _search_engine_initialized = True
        _search_index_metadata = dict(snapshot_metadata or {})

        logger.info(
            "Initialized Health/InBody BM25 index with %s documents",
            len(_documents),
        )
        return True
    except Exception as e:
        logger.error("Failed to initialize Health/InBody search index: %s", e)
        _search_engine_initialized = False
        _search_index_metadata = {}
        return False


def save_search_snapshot(
    snapshot_path: str | Path | None = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist normalized BM25 documents atomically without unsafe pickle."""
    global _search_index_metadata
    if not _search_engine_initialized or not _documents:
        logger.warning("Cannot persist BM25 snapshot before index initialization")
        return False

    path = Path(snapshot_path or BM25_SNAPSHOT_PATH)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": BM25_SNAPSHOT_SCHEMA_VERSION,
        "collection_name": DEFAULT_COLLECTION_NAME,
        "created_at": created_at,
        "document_count": len(_documents),
        "metadata": dict(metadata or {}),
        "documents": _documents,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(temporary_path, "wt", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
        temporary_path.replace(path)
        _search_index_metadata = {
            **_search_index_metadata,
            **(metadata or {}),
            "snapshot_persisted": True,
            "snapshot_path": str(path),
            "snapshot_created_at": created_at,
        }
        logger.info("Persisted BM25 snapshot with %s documents", len(_documents))
        return True
    except Exception as exc:
        logger.error("Failed to persist BM25 snapshot: %s", exc)
        try:
            temporary_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def load_search_snapshot(snapshot_path: str | Path | None = None) -> bool:
    """Load a trusted local JSON-gzip snapshot and rebuild the in-memory index."""
    path = Path(snapshot_path or BM25_SNAPSHOT_PATH)
    if not path.exists():
        logger.warning("BM25 snapshot is not available at configured path")
        return False
    try:
        with gzip.open(path, "rt", encoding="utf-8") as file:
            payload = json.load(file)
        if payload.get("schema_version") != BM25_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported BM25 snapshot schema")
        if payload.get("collection_name") != DEFAULT_COLLECTION_NAME:
            raise ValueError("BM25 snapshot collection does not match runtime collection")
        documents = payload.get("documents") or []
        if int(payload.get("document_count") or 0) != len(documents):
            raise ValueError("BM25 snapshot document count is inconsistent")
        metadata = {
            **(payload.get("metadata") or {}),
            "snapshot_loaded": True,
            "snapshot_path": str(path),
            "snapshot_created_at": payload.get("created_at"),
        }
        return initialize_search_index(documents, snapshot_metadata=metadata)
    except Exception as exc:
        logger.error("Failed to load BM25 snapshot: %s", exc)
        return False


def _bm25_candidate_indices(filters: Optional[Dict[str, Any]]) -> List[int] | range:
    """Narrow the common content-type filter before scoring the BM25 corpus."""
    if not filters or "content_type" not in filters:
        return range(len(_documents))

    expected = filters["content_type"]
    if isinstance(expected, str):
        allowed = [expected]
    elif isinstance(expected, (list, tuple, set)):
        allowed = [str(value) for value in expected]
    else:
        return range(len(_documents))

    index_by_type = _bm25_index.get("content_type_indices", {})
    return sorted(
        {
            index
            for content_type in allowed
            for index in index_by_type.get(content_type, [])
        }
    )


def bm25_search(
    query: str,
    limit: int = DEFAULT_TOP_K,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Tim kiem keyword BM25 trong in-memory Health/InBody index."""
    if not _search_engine_initialized or not _documents:
        return []

    expanded_query = expand_health_query(query)
    query_tokens = _tokenize(expanded_query)
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
        scored_docs.append((result, score))

    scored_docs.sort(key=lambda item: item[1], reverse=True)
    return [doc for doc, _ in scored_docs[:limit]]


def _get_embedding(query: str, timeout: float | None = None):
    """
    Lay embedding neu backend da implement.

    brain.py hien con skeleton trong project, nen ham nay fallback ve None khi
    embedding service chua san sang.
    """
    try:
        from llm.client import get_embedding

        return get_embedding(query, timeout=timeout)
    except Exception as e:
        logger.warning("Embedding is not available, vector search skipped: %s", e)
        return None


def vector_search_fallback(
    query: str,
    limit: int = DEFAULT_TOP_K,
    filters: Optional[Dict[str, Any]] = None,
    embedding_timeout: float | None = None,
) -> List[Dict]:
    """
    Tim kiem vector trong Qdrant neu embedding service va vector store san sang.
    """
    vector = _get_embedding(query, timeout=embedding_timeout)
    if vector is None:
        return []

    try:
        from rag.qdrant.client import search_vector

        results = search_vector(
            DEFAULT_COLLECTION_NAME,
            vector,
            limit=limit,
            filters=filters,
        )
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        return []

    for result in results:
        result["search_method"] = "vector"
        result["vector_score"] = result.get("similarity_score", 0)
        result["hybrid_score"] = result.get("similarity_score", 0)
        result.setdefault("domain", "health_inbody")
        result.setdefault(
            "content_type",
            _detect_content_type(_document_text(result)),
        )

    return results[:limit]


def _content_key(doc: Dict[str, Any]) -> str:
    return (doc.get("doc_id") or doc.get("content") or _document_text(doc)).__str__()


def _matches_filters(doc: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """Apply simple equality/range filters to non-Qdrant retrieval results."""
    if not filters:
        return True

    for field, expected in filters.items():
        actual = doc.get(field)
        if isinstance(expected, dict):
            if actual is None:
                return False
            if "gte" in expected and actual < expected["gte"]:
                return False
            if "lte" in expected and actual > expected["lte"]:
                return False
            if "gt" in expected and actual <= expected["gt"]:
                return False
            if "lt" in expected and actual >= expected["lt"]:
                return False
        elif isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def combine_search_results(
    bm25_results,
    vector_results,
    query: str,
    dense_weight: float = DEFAULT_DENSE_WEIGHT,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
) -> List[Dict]:
    """
    Gop ket qua BM25 va vector search thanh danh sach co hybrid_score.
    """
    combined: Dict[str, Dict[str, Any]] = {}

    bm25_scored = [
        (idx, float(doc.get("bm25_score", 0))) for idx, doc in enumerate(bm25_results)
    ]
    vector_scored = [
        (idx, float(doc.get("similarity_score", doc.get("vector_score", 0))))
        for idx, doc in enumerate(vector_results)
    ]
    normalized_bm25 = _normalize_scores(bm25_scored)
    normalized_vector = _normalize_scores(vector_scored)

    for idx, doc in enumerate(bm25_results):
        key = _content_key(doc)
        item = doc.copy()
        item["bm25_score"] = normalized_bm25.get(idx, 0.0)
        item["vector_score"] = 0.0
        item["search_method"] = "bm25"
        combined[key] = item

    for idx, doc in enumerate(vector_results):
        key = _content_key(doc)
        vector_score = normalized_vector.get(idx, 0.0)
        if key in combined:
            combined[key].update({k: v for k, v in doc.items() if v not in (None, "")})
            combined[key]["vector_score"] = vector_score
            combined[key]["search_method"] = "hybrid"
        else:
            item = doc.copy()
            item["bm25_score"] = 0.0
            item["vector_score"] = vector_score
            item["search_method"] = "vector"
            combined[key] = item

    query_content_type = _detect_content_type(query)
    for doc in combined.values():
        content_type = doc.get("content_type") or _detect_content_type(_document_text(doc))
        doc["content_type"] = content_type
        doc.setdefault("domain", "health_inbody")

        hybrid_bonus = 0.1 if doc.get("search_method") == "hybrid" else 0.0
        domain_bonus = 0.05 if content_type == query_content_type else 0.0
        doc["hybrid_score"] = round(
            (dense_weight * doc.get("vector_score", 0.0))
            + (bm25_weight * doc.get("bm25_score", 0.0))
            + hybrid_bonus
            + domain_bonus,
            6,
        )

    results = list(combined.values())
    results.sort(key=lambda doc: doc.get("hybrid_score", 0.0), reverse=True)
    logger.info("Combined %s hybrid search results for Health/InBody query", len(results))
    return results


def expand_parent_documents(
    docs: List[Dict[str, Any]],
    max_parents: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Expand retrieved child chunks to their parent documents while deduplicating by parent_id.
    Preserves the highest ranking/score among child matches for each parent.
    """
    if not docs:
        return []

    expanded_parents: List[Dict[str, Any]] = []
    seen_parent_keys: set[str] = set()

    for doc in docs:
        parent_id = doc.get("parent_id") or (doc.get("metadata") or {}).get("parent_id")
        parent_content = doc.get("parent_content") or (doc.get("metadata") or {}).get("parent_content")

        # Fallback if no parent or empty parent_content: use chunk itself
        if not parent_id or not parent_content:
            key = str(doc.get("chunk_id") or doc.get("doc_id") or doc.get("content") or "")
            if key not in seen_parent_keys:
                seen_parent_keys.add(key)
                expanded_parents.append(doc)
            if max_parents and len(expanded_parents) >= max_parents:
                break
            continue

        parent_key = str(parent_id)
        if parent_key in seen_parent_keys:
            # Already have this parent from a higher-scoring child chunk
            continue

        seen_parent_keys.add(parent_key)
        parent_doc = doc.copy()
        # Keep original child info for traceability
        parent_doc["child_content"] = doc.get("content", "")
        parent_doc["child_chunk_id"] = doc.get("chunk_id", "")
        # Expand content to full parent content
        parent_doc["content"] = parent_content
        if doc.get("parent_title"):
            parent_doc["title"] = doc["parent_title"]
        parent_doc["is_expanded_parent"] = True

        expanded_parents.append(parent_doc)
        if max_parents and len(expanded_parents) >= max_parents:
            break

    return expanded_parents


def hybrid_search(
    query: str,
    limit: int = DEFAULT_TOP_K,
    filters: Optional[Dict[str, Any]] = None,
    use_rerank: bool = True,
    embedding_timeout: float | None = None,
    expand_parents: Optional[bool] = None,
) -> List[Dict]:
    """
    Tim kiem hybrid cho Health/InBody RAG.

    Luong chay:
    1. Mo rong query theo thuat ngu Health/InBody.
    2. Chay BM25 neu index da duoc khoi tao.
    3. Chay vector search neu embedding/Qdrant san sang.
    4. Gop diem hybrid va rerank ket qua cuoi.
    5. Expand Child chunk thanh Parent document va deduplicate (Small-to-Big Retrieval).
    """
    if not query or not query.strip():
        return []

    should_expand = ENABLE_PARENT_RETRIEVAL if expand_parents is None else expand_parents
    candidate_limit = limit * 3 if should_expand else limit * 2

    expanded_query = expand_health_query(query)
    bm25_results = bm25_search(expanded_query, limit=candidate_limit, filters=filters)
    candidate_count = len(_bm25_candidate_indices(filters))
    bm25_covers_filtered_corpus = bool(
        filters
        and candidate_count
        and candidate_count <= candidate_limit
        and len(bm25_results) >= candidate_count
    )
    if bm25_covers_filtered_corpus:
        logger.info(
            "BM25 covered all %s filtered candidates; skipped redundant vector search",
            candidate_count,
        )
        vector_results = []
    else:
        vector_results = vector_search_fallback(
            expanded_query,
            limit=candidate_limit,
            filters=filters,
            embedding_timeout=embedding_timeout,
        )

    # Qdrant applies its filter server-side, but BM25 is process-local. Apply the
    # same policy here so a safety query cannot regain recipe/nutrition results
    # merely because dense retrieval is unavailable.
    bm25_results = [doc for doc in bm25_results if _matches_filters(doc, filters)]
    vector_results = [doc for doc in vector_results if _matches_filters(doc, filters)]

    if bm25_results or vector_results:
        combined = combine_search_results(bm25_results, vector_results, query)
    else:
        logger.warning("No BM25/vector results available for query: %s", query)
        combined = []

    if use_rerank and combined:
        rerank_pool = combined[:candidate_limit]
        reranked = rerank_documents(rerank_pool, query, top_n=candidate_limit)
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
    """Lay thong tin trang thai search index."""
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
        "snapshot_created_at": _search_index_metadata.get("snapshot_created_at"),
        "snapshot_point_count": _search_index_metadata.get("qdrant_point_count"),
        "corpus_version": _search_index_metadata.get("corpus_version"),
        "collection_name": DEFAULT_COLLECTION_NAME,
        "domain": "health_inbody",
    }


def force_initialize_if_needed() -> bool:
    """
    Thu khoi tao BM25 tu payload trong Qdrant neu index chua co.

    Neu Qdrant/embedding service chua san sang, ham tra False va hybrid_search
    van co the tiep tuc voi cac thanh phan con lai.
    """
    if _search_engine_initialized:
        return True

    return initialize_from_vector_store()


def initialize_from_vector_store(
    limit: int = 1000,
    vector_client: Any = None,
    persist_snapshot: bool = False,
    snapshot_path: str | Path | None = None,
) -> bool:
    """
    Load payload tu Qdrant de khoi tao BM25 index.
    """
    try:
        if vector_client is None:
            from rag.qdrant.client import client as vector_client

        points = []
        next_offset = None
        while True:
            page, next_offset = vector_client.scroll(
                collection_name=DEFAULT_COLLECTION_NAME,
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
        payload = point.payload or {}
        documents.append(
            {
                "question": payload.get("question", ""),
                "content": payload.get("content", ""),
                "source": payload.get("source", "vector_store"),
                "doc_id": payload.get("doc_id", point.id if point else index),
                "content_type": payload.get("content_type"),
                "domain": payload.get("domain", "health_inbody"),
            }
        )

    metadata = {
        "qdrant_point_count": len(points),
        "corpus_version": next(
            (
                str((point.payload or {}).get("corpus_version"))
                for point in points
                if (point.payload or {}).get("corpus_version")
            ),
            None,
        ),
    }
    initialized = initialize_search_index(documents, snapshot_metadata=metadata)
    if initialized and persist_snapshot:
        if not save_search_snapshot(snapshot_path=snapshot_path, metadata=metadata):
            return False
    return initialized

"""Pure functions for hybrid retrieval fusion and small-to-big parent document expansion.

Design principles (python-design-patterns):
- Single Responsibility & KISS: Pure scoring and merge operations without side effects or I/O.
- Deterministic data combining with explicit verification of chunk/release consistency.
"""
import hashlib
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from rag.bm25 import (
    HEALTH_DOMAIN_KEYWORDS,
    detect_content_type,
    extract_document_text,
)
from rag.corpus_lifecycle import (
    CorpusReleaseMismatchError,
    canonical_chunk_identity,
)

logger = logging.getLogger(__name__)

DEFAULT_DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.6"))
DEFAULT_BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.4"))


def normalize_scores(scored_docs: Sequence[Tuple[int, float]]) -> Dict[int, float]:
    """Normalize score values by max score into [0.0, 1.0] range."""
    if not scored_docs:
        return {}

    max_score = max(score for _, score in scored_docs) or 1.0
    return {idx: (score / max_score) for idx, score in scored_docs}


def canonical_content_key(doc: Dict[str, Any]) -> tuple:
    """Build unique identifying tuple for document chunk deduplication and fusion matching."""
    identity = canonical_chunk_identity(doc)
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    explicit_chunk = doc.get("chunk_id") or metadata.get("chunk_id")
    if identity["document_id"] and explicit_chunk:
        return ("chunk", identity["document_id"], identity["chunk_id"])
    if identity["content_hash"]:
        return ("content", identity["document_id"], identity["content_hash"])
    return ("point", identity["qdrant_point_id"])


def assert_same_chunk_consistency(
    first: Dict[str, Any],
    second: Dict[str, Any],
) -> None:
    """Validate that two representations of the same chunk do not have conflicting content/release."""
    a, b = canonical_chunk_identity(first), canonical_chunk_identity(second)
    for field in ("content_hash",):
        if a[field] and b[field] and a[field] != b[field]:
            raise CorpusReleaseMismatchError("Conflicting chunk content")
    for field in ("release_id", "corpus_version", "active_physical_collection"):
        if first.get(field) and second.get(field) and first[field] != second[field]:
            raise CorpusReleaseMismatchError("Conflicting chunk release")


def combine_search_results(
    bm25_results: Sequence[Dict[str, Any]],
    vector_results: Sequence[Dict[str, Any]],
    query: str,
    dense_weight: float = DEFAULT_DENSE_WEIGHT,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
    domain_keywords: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """Gop ket qua BM25 va vector search thanh danh sach co hybrid_score trung thuc."""
    combined: Dict[tuple, Dict[str, Any]] = {}
    both_branches_present = bool(bm25_results) and bool(vector_results)

    bm25_scored = [
        (idx, float(doc.get("bm25_score", 0))) for idx, doc in enumerate(bm25_results)
    ]
    vector_scored = [
        (idx, float(doc.get("similarity_score", doc.get("vector_score", 0))))
        for idx, doc in enumerate(vector_results)
    ]
    normalized_bm25 = normalize_scores(bm25_scored)
    normalized_vector = normalize_scores(vector_scored)

    for idx, doc in enumerate(bm25_results):
        key = canonical_content_key(doc)
        if key in combined:
            assert_same_chunk_consistency(combined[key], doc)
            continue
        item = doc.copy()
        item["bm25_score"] = normalized_bm25.get(idx, 0.0)
        item["vector_score"] = 0.0
        item["search_method"] = "bm25"
        item["retrieval_mode"] = "hybrid" if both_branches_present else "bm25_only"
        combined[key] = item

    for idx, doc in enumerate(vector_results):
        key = canonical_content_key(doc)
        vector_score = normalized_vector.get(idx, 0.0)
        if key in combined:
            assert_same_chunk_consistency(combined[key], doc)
            combined[key].update({k: v for k, v in doc.items() if v not in (None, "")})
            combined[key]["vector_score"] = vector_score
            combined[key]["search_method"] = "hybrid"
            combined[key]["retrieval_mode"] = "hybrid"
        else:
            item = doc.copy()
            item["bm25_score"] = 0.0
            item["vector_score"] = vector_score
            item["search_method"] = "vector"
            item["retrieval_mode"] = "hybrid" if both_branches_present else "dense_only"
            combined[key] = item

    query_content_type = detect_content_type(query, domain_keywords=domain_keywords)
    for doc in combined.values():
        content_type = doc.get("content_type") or detect_content_type(
            extract_document_text(doc), domain_keywords=domain_keywords
        )
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
    logger.info(
        "Combined %s search results (mode=%s)",
        len(results),
        "hybrid"
        if both_branches_present
        else ("bm25_only" if bm25_results else "dense_only"),
    )
    return results


def expand_parent_documents(
    docs: Sequence[Dict[str, Any]],
    max_parents: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Expand retrieved child chunks to their parent documents while deduplicating by parent_id."""
    if not docs:
        return []

    expanded_parents: List[Dict[str, Any]] = []
    seen_parent_keys: Set[Any] = set()
    parents: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for doc in docs:
        parent_id = doc.get("parent_id") or (doc.get("metadata") or {}).get("parent_id")
        parent_content = doc.get("parent_content") or (doc.get("metadata") or {}).get(
            "parent_content"
        )

        if not parent_id or not parent_content:
            key = canonical_content_key(doc)
            if key not in seen_parent_keys and (
                not max_parents or len(expanded_parents) < max_parents
            ):
                seen_parent_keys.add(key)
                expanded_parents.append(doc)
            continue

        parent_key = (
            str(
                doc.get("document_id")
                or (doc.get("metadata") or {}).get("document_id")
                or ""
            ),
            str(parent_id),
        )
        child_identity = canonical_chunk_identity(doc)
        if parent_key in parents:
            parent = parents[parent_key]
            if parent["content"] != parent_content:
                raise CorpusReleaseMismatchError("Conflicting parent content")
            if child_identity not in parent["matched_children"]:
                parent["matched_children"].append(child_identity)
            continue

        if max_parents and len(expanded_parents) >= max_parents:
            continue

        seen_parent_keys.add(parent_key)
        parent_doc = doc.copy()
        nested_meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        parent_doc["child_content"] = doc.get("content", "")
        parent_doc["child_chunk_id"] = str(
            doc.get("chunk_id") or doc.get("doc_id") or ""
        )
        parent_doc["parent_id"] = str(parent_id)
        parent_doc["document_id"] = str(
            doc.get("document_id")
            or nested_meta.get("document_id")
            or nested_meta.get("doc_id")
            or doc.get("doc_id")
            or str(parent_id)
        )
        parent_doc["chunk_id"] = str(parent_id)
        parent_doc["matched_children"] = [child_identity]
        parent_doc["evidence_scope"] = "parent_section"
        parent_doc["content"] = parent_content
        parent_doc["content_hash"] = hashlib.sha256(
            parent_content.encode("utf-8")
        ).hexdigest()
        if doc.get("parent_title"):
            parent_doc["title"] = doc["parent_title"]
        parent_doc["is_expanded_parent"] = True

        expanded_parents.append(parent_doc)
        parents[parent_key] = parent_doc

    return expanded_parents

"""Allocate citations only after admission into the composer context."""

from typing import Any, Dict, List, Mapping, Optional, Tuple

from harness.layers.injection_guard import clean_retrieved_document
from rag.provenance import is_verified_medical_review, normalize_evidence_provenance


def _sanitize_parent_scope(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Ensure parent-expanded chunks carry explicit parent provenance.

    If a document claims parent expansion without a parent_id, fall back to its
    child_content rather than misattributing parent text to a child chunk_id.
    """
    if not doc.get("is_expanded_parent"):
        return doc
    parent_id = str(doc.get("parent_id") or "").strip()
    if parent_id:
        safe = dict(doc)
        safe["parent_id"] = parent_id
        safe["chunk_id"] = parent_id
        safe["evidence_scope"] = "parent_section"
        return safe
    child_content = str(doc.get("child_content") or "").strip()
    if not child_content:
        return None
    safe = dict(doc)
    safe["content"] = child_content
    safe["is_expanded_parent"] = False
    safe["evidence_scope"] = "chunk"
    return safe


def build_evidence(
    docs: List[Dict[str, Any]],
    *,
    review_registry: Optional[Mapping[str, Any]] = None,
    allow_synthetic_registry: bool = False,
    _admitted_provenance: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for doc_index, doc in enumerate(docs):
        scoped = _sanitize_parent_scope(doc)
        if scoped is None:
            continue
        nested_meta = scoped.get("metadata") if isinstance(scoped.get("metadata"), dict) else {}
        document_id = (
            scoped.get("document_id")
            or nested_meta.get("document_id")
            or scoped.get("doc_id")
            or nested_meta.get("doc_id")
            or scoped.get("id")
        )
        content = scoped.get("content") or ""
        if not document_id or not content:
            continue
        provenance = _admitted_provenance[doc_index] if _admitted_provenance is not None else normalize_evidence_provenance(
            scoped,
            registry=review_registry,
            allow_synthetic_registry=allow_synthetic_registry,
        )
        is_parent = bool(scoped.get("is_expanded_parent"))
        parent_id = str(scoped.get("parent_id") or "").strip() or None
        chunk_id = (
            parent_id
            if is_parent and parent_id
            else str(scoped.get("chunk_id") or nested_meta.get("chunk_id") or scoped.get("id") or document_id)
        )
        index = len(evidence) + 1
        item: Dict[str, Any] = {
            "id": index,
            "document_id": str(document_id),
            "chunk_id": str(chunk_id),
            "title": scoped.get("title") or scoped.get("question") or f"Tài liệu {index}",
            "source": scoped.get("source") or scoped.get("source_file") or "unknown",
            "source_url": provenance["source_url"],
            "publisher": provenance["publisher"],
            "source_tier": provenance["source_tier"],
            "source_tier_verified": provenance["source_tier_verified"],
            "published_at": provenance["published_at"],
            "reviewed_at": provenance["reviewed_at"],
            "medical_review_status": provenance["medical_review_status"],
            "review_verification_status": provenance["review_verification_status"],
            "review_id": provenance["review_id"],
            "reviewer_id": provenance["reviewer_id"],
            "review_scope": provenance["review_scope"],
            "privacy_review_status": provenance["privacy_review_status"],
            "content_type": scoped.get("content_type"),
            "excerpt": content,
            "source_version": (
                scoped.get("corpus_version")
                or nested_meta.get("corpus_version")
                or scoped.get("source_version")
            ),
            "content_hash": scoped.get("content_hash") or nested_meta.get("content_hash"),
            "document_content_hash": provenance["document_content_hash"],
            "evidence_scope": "parent_section" if is_parent else (scoped.get("evidence_scope") or "chunk"),
            "is_expanded_parent": is_parent,
            "parent_id": parent_id,
            "matched_child_chunk_id": (
                str(scoped.get("child_chunk_id") or "").strip() or None
                if is_parent
                else None
            ),
            "retrieval_score": scoped.get("similarity_score", scoped.get("hybrid_score")),
            "rerank_score": scoped.get("rerank_score"),
        }
        if is_parent and scoped.get("child_content"):
            item["child_excerpt"] = str(scoped["child_content"])
        evidence.append(item)
    return evidence


def prepare_composer_context(
    docs: List[Dict[str, Any]],
    *,
    max_docs: int,
    max_chars: int,
    require_verified_medical_review: bool = False,
    review_registry: Optional[Mapping[str, Any]] = None,
    allow_synthetic_registry: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    admitted: List[Dict[str, Any]] = []
    admitted_provenance: List[Dict[str, Any]] = []
    rejected = 0
    for doc in docs:
        if len(admitted) >= max_docs:
            break
        scoped = _sanitize_parent_scope(doc) if isinstance(doc, dict) else None
        if scoped is None:
            rejected += 1
            continue
        provenance = normalize_evidence_provenance(
            scoped, registry=review_registry, allow_synthetic_registry=allow_synthetic_registry,
        )
        safe = clean_retrieved_document(scoped, max_chars)
        if safe is None:
            rejected += 1
            continue
        safe.update(provenance)
        if require_verified_medical_review and not is_verified_medical_review(provenance):
            rejected += 1
            continue
        admitted.append(safe)
        admitted_provenance.append(provenance)
    evidence = build_evidence(
        admitted,
        review_registry=review_registry,
        allow_synthetic_registry=allow_synthetic_registry,
        _admitted_provenance=admitted_provenance,
    )
    return admitted, evidence, rejected

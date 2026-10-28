"""Allocate citations only after admission into the composer context."""

from typing import Any, Dict, List, Tuple

from harness.layers.injection_guard import clean_retrieved_document


def build_evidence(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evidence = []
    for doc in docs:
        document_id = doc.get("document_id") or doc.get("doc_id") or doc.get("id")
        content = doc.get("content") or ""
        if not document_id or not content:
            continue
        index = len(evidence) + 1
        evidence.append({
            "id": index,
            "document_id": str(document_id),
            "chunk_id": str(doc.get("chunk_id") or doc.get("id") or document_id),
            "title": doc.get("title") or doc.get("question") or f"Tài liệu {index}",
            "source": doc.get("source") or doc.get("source_file") or "unknown",
            "source_url": doc.get("source_url"),
            "publisher": doc.get("publisher"),
            "source_tier": doc.get("source_tier"),
            "published_at": doc.get("published_at"),
            "reviewed_at": doc.get("reviewed_at"),
            "content_type": doc.get("content_type"),
            "excerpt": content,
            "source_version": doc.get("corpus_version") or doc.get("source_version"),
            "retrieval_score": doc.get("similarity_score", doc.get("hybrid_score")),
            "rerank_score": doc.get("rerank_score"),
        })
    return evidence


def prepare_composer_context(docs: List[Dict[str, Any]], *, max_docs: int,
                             max_chars: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    admitted = []
    rejected = 0
    for doc in docs:
        if len(admitted) >= max_docs:
            break
        safe = clean_retrieved_document(doc, max_chars)
        if safe is None:
            rejected += 1
        else:
            admitted.append(safe)
    return admitted, build_evidence(admitted), rejected

"""Rerank tai lieu truy xuat cho Health/InBody RAG."""
import logging
import os
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
DEFAULT_RANK_MODEL = os.environ.get("COHERE_RERANK_MODEL", "rerank-multilingual-v3.0")

HEALTH_KEYWORDS = {
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
        "phần trăm mỡ",
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


def _get_cohere_client():
    """Khoi tao Cohere client khi thuc su can, tranh loi import khi khong dung."""
    if not COHERE_API_KEY:
        return None

    try:
        import cohere

        return cohere.Client(COHERE_API_KEY)
    except Exception as e:
        logger.warning("Cohere reranker is not available: %s", e)
        return None


def _doc_to_text(doc: Any) -> str:
    """Lay text tu dict hoac LangChain Document."""
    if isinstance(doc, dict):
        title = doc.get("title", "") or ""
        content = doc.get("content", "") or doc.get("page_content", "") or ""
        source = doc.get("source", "") or doc.get("source_file", "") or ""
        return f"{title}\n{content}\n{source}".strip()

    page_content = getattr(doc, "page_content", "") or ""
    metadata = getattr(doc, "metadata", {}) or {}
    title = metadata.get("title", "") or ""
    source = metadata.get("source", "") or metadata.get("source_file", "") or ""
    return f"{title}\n{page_content}\n{source}".strip()


def _copy_doc_with_score(doc: Any, score: float, score_name: str = "relevance_score"):
    """Tra ve ban sao doc kem score, ho tro ca dict lan LangChain Document."""
    if isinstance(doc, dict):
        copied = doc.copy()
        copied[score_name] = score
        return copied

    try:
        copied = doc.copy(deep=True)
    except Exception:
        copied = doc

    metadata = dict(getattr(copied, "metadata", {}) or {})
    metadata[score_name] = score
    copied.metadata = metadata
    return copied


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[\wÀ-ỹ]+", text.lower())


def _detect_query_domain(query: str) -> str:
    query_lower = query.lower()
    for domain, keywords in HEALTH_KEYWORDS.items():
        if any(keyword in query_lower for keyword in keywords):
            return domain
    return "general_health"


def _metadata_of(doc: Any) -> Dict[str, Any]:
    if isinstance(doc, dict):
        return doc
    return getattr(doc, "metadata", {}) or {}


def _heuristic_score(doc: Any, query: str) -> float:
    """
    Cham diem fallback khi khong co Cohere.

    Diem gom overlap tu khoa voi query, diem vector search neu co, va boost nhe
    neu content_type cua chunk khop voi domain cau hoi Health/InBody.
    """
    text = _doc_to_text(doc)
    metadata = _metadata_of(doc)
    query_tokens = set(_tokenize(query))
    doc_tokens = set(_tokenize(text))

    if not doc_tokens:
        return 0.0

    overlap = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)
    vector_score = float(metadata.get("similarity_score") or metadata.get("score") or 0.0)

    query_domain = _detect_query_domain(query)
    content_type = metadata.get("content_type", "")
    domain_boost = 0.15 if content_type == query_domain else 0.0
    health_boost = 0.05 if metadata.get("domain") == "health_inbody" else 0.0

    return round(overlap + (0.35 * vector_score) + domain_boost + health_boost, 6)


def _rerank_with_cohere(
    docs: List[Any],
    query: str,
    top_n: int,
    rank_model: str,
) -> Tuple[List[Any], bool]:
    client = _get_cohere_client()
    if client is None:
        return [], False

    process_docs = []
    valid_doc_indices = []
    for idx, doc in enumerate(docs):
        combined = _doc_to_text(doc)
        if combined:
            process_docs.append(combined)
            valid_doc_indices.append(idx)

    if not process_docs:
        return [], False

    try:
        logger.info(
            "Reranking %s Health/InBody docs with Cohere model=%s",
            len(process_docs),
            rank_model,
        )
        results = client.rerank(
            query=query,
            documents=process_docs,
            top_n=min(top_n, len(process_docs)),
            model=rank_model,
        )

        ranked_docs = []
        for item in results.results:
            original_idx = valid_doc_indices[item.index]
            ranked_docs.append(
                _copy_doc_with_score(docs[original_idx], item.relevance_score)
            )
        return ranked_docs, True
    except Exception as e:
        logger.warning("Cohere rerank failed, falling back to local scoring: %s", e)
        return [], False


def _rerank_with_health_heuristic(docs: List[Any], query: str, top_n: int) -> List[Any]:
    scored_docs = []
    for doc in docs:
        score = _heuristic_score(doc, query)
        scored_docs.append(_copy_doc_with_score(doc, score))

    scored_docs.sort(
        key=lambda doc: (
            _metadata_of(doc).get("relevance_score", 0.0),
            _metadata_of(doc).get("similarity_score", 0.0),
        ),
        reverse=True,
    )
    return scored_docs[:top_n]


def rerank_documents(docs, query, top_n=5, rank_model=DEFAULT_RANK_MODEL):
    """
    Sap xep lai tai lieu truy xuat theo do phu hop voi cau hoi Health/InBody.

    Uu tien Cohere multilingual rerank neu co COHERE_API_KEY. Neu khong co API
    key hoac request loi, ham se fallback sang scoring cuc bo dua tren keyword
    overlap, similarity_score va metadata content_type/domain.

    Args:
        docs: Danh sach document dang dict hoac LangChain Document.
        query: Cau hoi/truy van cua nguoi dung.
        top_n: So tai lieu cuoi cung can lay.
        rank_model: Ten model rerank cua Cohere.

    Returns:
        Danh sach document da duoc gan relevance_score va sap xep giam dan.
    """
    if not docs:
        logger.info("Docs list is empty, skipping rerank")
        return []

    if not query or not query.strip():
        logger.info("Query is empty, returning original docs without rerank")
        return docs[:top_n]

    ranked_docs, used_external_reranker = _rerank_with_cohere(
        docs=docs,
        query=query,
        top_n=top_n,
        rank_model=rank_model,
    )
    if used_external_reranker:
        return ranked_docs

    logger.info("Using local Health/InBody heuristic reranker for %s docs", len(docs))
    return _rerank_with_health_heuristic(docs, query, top_n)

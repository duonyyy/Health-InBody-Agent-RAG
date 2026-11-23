"""Pure functions and lexical indexing utilities for BM25 keyword search.

Design principles (python-design-patterns):
- KISS & Separation of Concerns: Pure data transformations without global state or I/O.
- Deterministic logic separated from storage, retrieval I/O, and model calls.
"""
from collections import Counter
import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from rag.provenance import PROVENANCE_METADATA_FIELDS

HEALTH_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
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

RECIPE_MARKERS: Tuple[str, ...] = (
    "công thức món",
    "công thức nấu",
    "nguyên liệu:",
    "cách chế biến:",
    "hướng dẫn nấu",
    "muỗng canh",
    "muỗng cà phê",
    "thìa cà phê",
    "hầm 45 phút",
    "hầm 30 phút",
)


def normalize_lexical_text(text: str) -> str:
    """Normalize Vietnamese accents so legacy ASCII documents remain searchable."""
    lowered = (text or "").lower().replace("đ", "d")
    return "".join(
        character
        for character in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(character) != "Mn"
    )


def tokenize(text: str) -> List[str]:
    """Extract word tokens after lexical accent normalization."""
    return re.findall(r"\w+", normalize_lexical_text(text))


def extract_document_text(doc: Dict[str, Any]) -> str:
    """Extract searchable textual representation from document dictionary."""
    title = doc.get("title", "") or doc.get("question", "") or ""
    content = doc.get("content", "") or doc.get("page_content", "") or ""
    source = doc.get("source", "") or doc.get("source_file", "") or ""
    return f"{title}\n{content}\n{source}".strip()


def detect_content_type(
    text: str,
    domain_keywords: Optional[Dict[str, List[str]]] = None,
) -> str:
    """Detect health content domain from text using keyword heuristics."""
    text_lower = (text or "").lower()
    keywords_dict = domain_keywords or HEALTH_DOMAIN_KEYWORDS
    for content_type, keywords in keywords_dict.items():
        if any(keyword in text_lower for keyword in keywords):
            return content_type
    return "general_health"


def is_recipe_document(doc: Dict[str, Any]) -> bool:
    """Detect whether a document contains culinary recipes rather than clinical/safety evidence."""
    if doc.get("is_recipe") is True:
        return True
    meta = doc.get("metadata") or {}
    if meta.get("is_recipe") is True or meta.get("document_kind") == "recipe":
        return True
    text = (doc.get("content") or "").lower()
    title = (doc.get("title") or "").lower()
    return any(marker in text or marker in title for marker in RECIPE_MARKERS)


def matches_document_filters(
    doc: Dict[str, Any],
    filters: Optional[Dict[str, Any]],
) -> bool:
    """Apply simple equality/range filters to retrieval documents.

    Rule: Medical safety retrieval MUST filter out recipe documents (AGENTS.md rule 8).
    """
    if not filters:
        return True

    if filters.get("content_type") == "medical_safety" or filters.get("exclude_recipe"):
        if is_recipe_document(doc):
            return False

    for field, expected in filters.items():
        if field == "exclude_recipe":
            continue
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


def normalize_search_document(
    doc: Dict[str, Any],
    index: int,
) -> Optional[Dict[str, Any]]:
    """Normalize raw document payload into canonical document schema for BM25 indexing."""
    text = extract_document_text(doc)
    if not text:
        return None

    doc_metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    doc_id = str(doc.get("doc_id", doc.get("id", index)))
    document_id = str(
        doc.get("document_id")
        or doc_metadata.get("document_id")
        or doc_metadata.get("doc_id")
        or doc_id
    )
    chunk_id = str(doc.get("chunk_id") or doc_metadata.get("chunk_id") or doc_id)

    normalized = {
        "title": doc.get("title", "") or doc.get("question", ""),
        "question": doc.get("question", ""),
        "content": doc.get("content", "") or doc.get("page_content", ""),
        "source": (
            doc.get("source", "")
            or doc.get("source_file", "")
            or doc_metadata.get("source", "")
            or doc_metadata.get("source_file", "unknown")
        ),
        "doc_id": doc_id,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "content_type": doc.get("content_type") or detect_content_type(text),
        "domain": doc.get("domain", "health_inbody"),
    }

    for key, value in doc.items():
        normalized.setdefault(key, value)

    for field in PROVENANCE_METADATA_FIELDS:
        if field not in normalized and field in doc_metadata:
            normalized[field] = doc_metadata[field]

    return normalized


def build_bm25_index(documents: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Build in-memory BM25 index data structures from normalized documents."""
    tokenized_docs = [tokenize(extract_document_text(doc)) for doc in documents]
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


def compute_bm25_score(
    query_tokens: Sequence[str],
    doc_index: int,
    bm25_index: Dict[str, Any],
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Calculate Okapi BM25 score for a document index against query tokens."""
    tokenized_docs = bm25_index.get("tokenized_docs", [])
    if doc_index >= len(tokenized_docs):
        return 0.0

    doc_tokens = tokenized_docs[doc_index]
    if not doc_tokens:
        return 0.0

    term_freq = Counter(doc_tokens)
    doc_freq = bm25_index.get("doc_freq", Counter())
    doc_count = bm25_index.get("doc_count", 0)
    avg_doc_len = bm25_index.get("avg_doc_len", 0) or 1
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


def get_bm25_candidate_indices(
    total_documents: int,
    bm25_index: Dict[str, Any],
    filters: Optional[Dict[str, Any]],
) -> Union[List[int], range]:
    """Narrow candidate document indices using content_type index lookup."""
    if not filters or "content_type" not in filters:
        return range(total_documents)

    expected = filters["content_type"]
    if isinstance(expected, str):
        allowed = [expected]
    elif isinstance(expected, (list, tuple, set)):
        allowed = [str(value) for value in expected]
    else:
        return range(total_documents)

    index_by_type = bm25_index.get("content_type_indices", {})
    return sorted(
        {
            index
            for content_type in allowed
            for index in index_by_type.get(content_type, [])
            if index < total_documents
        }
    )


def score_bm25_corpus(
    documents: Sequence[Dict[str, Any]],
    bm25_index: Dict[str, Any],
    query: str,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    k1: float = 1.5,
    b: float = 0.75,
) -> List[Dict[str, Any]]:
    """Pure search function executing BM25 scoring over documents without global state."""
    if not documents or not bm25_index:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    candidate_indices = get_bm25_candidate_indices(len(documents), bm25_index, filters)
    scored_docs: List[Tuple[Dict[str, Any], float]] = []

    for index in candidate_indices:
        doc = documents[index]
        if not matches_document_filters(doc, filters):
            continue
        score = compute_bm25_score(query_tokens, index, bm25_index, k1=k1, b=b)
        if score <= 0.0:
            continue

        result = doc.copy()
        result["bm25_score"] = score
        result["search_method"] = "bm25"
        result["retrieval_mode"] = "bm25_only"
        scored_docs.append((result, score))

    scored_docs.sort(key=lambda item: item[1], reverse=True)
    return [doc for doc, _ in scored_docs[:limit]]

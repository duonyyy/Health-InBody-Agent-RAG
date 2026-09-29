"""Deterministic untrusted-context and citation guards.

This is deliberately conservative. Token overlap permits close paraphrases,
but it is not a medical entailment model or a substitute for expert review.
"""

import re
import unicodedata
from typing import Any, Dict, List, Tuple


def _normalize_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks.replace("đ", "d")).strip()


INJECTION_MARKERS = (
    "ignore previous instructions", "disregard previous instructions",
    "reveal user health profile", "reveal system prompt", "print api key",
    "bỏ qua hướng dẫn", "bỏ qua cảnh báo", "tiết lộ hồ sơ",
    "tiết lộ dữ liệu", "tiết lộ api key", "không cần cảnh báo",
    "system: ignore", "developer: ignore", "system prompt:",
    "role=system", "role: system", "hãy bỏ cảnh báo",
    "bỏ qua kiểm tra an toàn", "in hồ sơ sức khỏe",
)


def has_untrusted_instruction(text: str) -> bool:
    normalized = _normalize_match_text(str(text or ""))
    return any(_normalize_match_text(marker) in normalized for marker in INJECTION_MARKERS)


def has_conflicting_evidence(docs: List[Dict[str, Any]]) -> bool:
    """Flag explicit conflicts or incompatible numbers for the same titled topic."""
    by_title: Dict[str, set[tuple[str, ...]]] = {}
    for doc in docs:
        if doc.get("evidence_conflict") or doc.get("conflicts_with"):
            return True
        title = _normalize_match_text(str(doc.get("title") or doc.get("question") or ""))
        numbers = tuple(sorted(set(re.findall(r"\d+(?:[.,]\d+)?", str(doc.get("content") or "")))))
        if title and numbers:
            by_title.setdefault(title, set()).add(numbers)
    return any(len(values) > 1 for values in by_title.values())


def suggests_unsafe_medical_change(text: str) -> bool:
    normalized = _normalize_match_text(text)
    return any(marker in normalized for marker in (
        "tap nang hon", "tang lieu thuoc", "ngung thuoc", "bo thuoc",
        "an kieng cuc doan", "tang cuong do tap",
    ))


def _claim_tokens(text: str) -> set[str]:
    stopwords = {"la", "cua", "va", "trong", "co", "the", "duoc", "mot", "nhung", "voi", "cho"}
    return set(re.findall(r"[a-z0-9]+", _normalize_match_text(text))) - stopwords


def verify_answer_claims(answer: str, evidence: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Fail closed when a sentence lacks a context citation or enough lexical support."""
    by_id = {str(item["id"]): item for item in evidence}
    claims = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", answer or "") if part.strip()]
    if not claims:
        return False, []
    links = []
    for index, claim in enumerate(claims, 1):
        cited = re.findall(r"\[(\d+)\]", claim)
        if not cited or any(ref not in by_id for ref in cited):
            return False, []
        plain = re.sub(r"\[\d+\]", "", claim).strip()
        tokens = _claim_tokens(plain)
        if not tokens:
            return False, []
        for ref in cited:
            item = by_id[ref]
            excerpt = item.get("excerpt") or ""
            evidence_tokens = _claim_tokens(excerpt)
            claim_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", plain))
            evidence_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", excerpt))
            if (len(tokens & evidence_tokens) / len(tokens) < 0.65
                    or not claim_numbers.issubset(evidence_numbers)
                    or ("khong" in _claim_tokens(plain) and "khong" not in _claim_tokens(excerpt))
                    or ("chan doan" in _normalize_match_text(plain)
                        and "chan doan" not in _normalize_match_text(excerpt))):
                return False, []
            links.append({
                "claim_id": index,
                "evidence_id": item["id"],
                "document_id": item["document_id"],
                "chunk_id": item["chunk_id"],
            })
    return True, links

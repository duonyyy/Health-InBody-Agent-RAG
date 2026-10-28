"""Strict cache policy and key construction for public RAG composer responses."""

import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional


_PERSONAL_OR_CLINICAL_QUERY = re.compile(
    r"\b(?:"
    r"toi|minh|em|chau|to|tao|cua toi|cua minh|"
    r"benh|benh nen|dau|trieu chung|thuoc|tieu duong|dai thao duong|"
    r"huyet ap|tim mach|than|gan|ung thu|di ung|mang thai|thai ky|"
    r"chan doan|dieu tri|lieu|patient|my|me|i|diagnos\w*|medicat\w*|symptom\w*"
    r")\b",
    re.IGNORECASE,
)
_QUERY_HAS_NUMBER = re.compile(r"\d")
_QUERY_HAS_IDENTIFIER = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b(?:ten toi|ten minh|ho va ten|"
    r"email|so dien thoai|dia chi nha|ma nguoi dung)\b)",
    re.IGNORECASE,
)
_GENERIC_DEFINITION_QUERY = re.compile(
    r"^(?:(?:giai thich|dinh nghia|y nghia cua|what is|what does)\s+)?"
    r"(?:chi so\s+)?(?:bmi|pbf|smm|bfm|inbody|mo noi tang|"
    r"chi so khoi co the|phan tram mo co the|khoi luong co xuong|"
    r"body mass index|body fat percentage|skeletal muscle mass)"
    r"(?:\s+(?:la gi|co nghia la gi|nghia la gi|co y nghia gi|"
    r"la chi so gi|mean|means|meaning|stands for))?[?.!\s]*$",
    re.IGNORECASE,
)
_ALLOWED_EMPTY_CONTEXT_KEYS = {"available", "reason"}
RESPONSE_CACHE_SCHEMA_VERSION = "health-inbody-rag-response-v1"


def _has_personal_data(context: Any) -> bool:
    if not context:
        return False
    if not isinstance(context, dict):
        return True
    if context.get("available"):
        return True
    for key, value in context.items():
        if key in _ALLOWED_EMPTY_CONTEXT_KEYS:
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def _normalize_query(text: str) -> str:
    lowered = (text or "").lower().replace("đ", "d")
    unmarked = "".join(
        character
        for character in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"\s+", " ", unmarked).strip()


def is_cacheable_public_rag_request(
    *,
    question: str,
    selected_agents: List[str],
    rag_agent: str,
    safety_result: Dict[str, Any],
    user_id: Optional[str],
    history: Optional[List[Dict[str, str]]],
    personalization_context: Any,
    user_profile: Any,
    memory_context: Optional[str],
    tool_results: Optional[List[Dict[str, Any]]],
    errors: Optional[List[str]],
    has_untrusted_input: bool = False,
) -> bool:
    """Fail closed unless the request is generic, stateless, and low risk."""
    text = str(question or "").strip()
    risk_level = (safety_result or {}).get("risk_level")
    if not text or risk_level != "low" or (safety_result or {}).get("conditions"):
        return False
    if selected_agents != [rag_agent] or user_id:
        return False
    if history or memory_context or tool_results or errors or has_untrusted_input:
        return False
    if _has_personal_data(personalization_context) or _has_personal_data(user_profile):
        return False
    normalized_text = _normalize_query(text)
    if (
        _QUERY_HAS_NUMBER.search(text)
        or _PERSONAL_OR_CLINICAL_QUERY.search(normalized_text)
        or _QUERY_HAS_IDENTIFIER.search(normalized_text)
        or not _GENERIC_DEFINITION_QUERY.fullmatch(normalized_text)
    ):
        return False
    return True


def build_llm_response_cache_key(
    *,
    messages: List[Dict[str, str]],
    model_config: Dict[str, Any],
    corpus_fingerprint: Dict[str, Any],
) -> str:
    """Build a deterministic opaque key; raw messages never appear in Redis keys."""
    corpus_version = str((corpus_fingerprint or {}).get("corpus_version") or "").strip()
    if corpus_version.lower() in {"", "unknown", "unversioned", "none"}:
        raise ValueError("A verified corpus_version is required for response caching")

    material = {
        "schema": RESPONSE_CACHE_SCHEMA_VERSION,
        "messages": messages,
        "model_config": model_config,
        "corpus_fingerprint": corpus_fingerprint,
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return f"llm-response:{RESPONSE_CACHE_SCHEMA_VERSION}:{digest}"

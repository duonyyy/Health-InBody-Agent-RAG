"""Sanitize retrieved text before it crosses into the composer prompt."""

import re
from typing import Any, Dict, Optional

from harness.guards import has_untrusted_instruction


_OPEN = re.compile(r"---\s*LƯU Ý HỆ THỐNG\b[^\n]*", re.IGNORECASE)
_CLOSE = re.compile(r"---\s*HẾT LƯU Ý HỆ THỐNG\s*---", re.IGNORECASE)
_REMOVED = "[nội dung không đáng tin cậy đã bị loại bỏ]"


def _remove_marked_blocks(content: str) -> str:
    """Discard an unclosed attacker block's tail, not the whole useful chunk."""
    while True:
        start = _OPEN.search(content)
        if start is None:
            return content
        end = _CLOSE.search(content, start.end())
        content = content[:start.start()] + _REMOVED + (content[end.end():] if end else "")


def clean_retrieved_document(doc: Dict[str, Any], max_chars: int) -> Optional[Dict[str, Any]]:
    if not isinstance(doc, dict) or max_chars < 1:
        return None
    document_id = doc.get("document_id") or doc.get("doc_id") or doc.get("id")
    content = str(doc.get("content") or doc.get("page_content") or "")
    if not document_id or not content.strip():
        return None
    content = _remove_marked_blocks(content).strip()
    metadata = " ".join(str(doc.get(key) or "") for key in ("title", "question", "source"))
    if not content or has_untrusted_instruction(metadata + " " + content):
        return None
    safe = dict(doc)
    safe["content"] = content[:max_chars]
    safe.pop("page_content", None)
    return safe


def clean_web_result(result: str) -> Optional[str]:
    text = str(result or "")
    cleaned = _remove_marked_blocks(text).strip()
    if not cleaned or has_untrusted_instruction(cleaned):
        return None
    return cleaned

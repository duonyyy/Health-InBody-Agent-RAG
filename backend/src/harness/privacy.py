"""Privacy and Personally Identifiable Information (PII) sanitization.

Provides deterministic masking and detection for sensitive demographic,
financial, and secret credentials in accordance with health data privacy guidelines.
"""

from __future__ import annotations

import re
from typing import Dict, List, Pattern, Tuple

# Patterns for sensitive entities in Vietnamese and international contexts
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Vietnamese mobile numbers (10 digits starting with 03, 05, 07, 08, 09 or +84, supporting 4-3-3, 3-3-4, and unbroken formats)
_PHONE_RE = re.compile(
    r"(?:\+84|0)(?:3[2-9]|5[689]|7[06-9]|8[1-9]|9\d)(?:[\s.-]?\d){7}\b"
)

# Vietnamese 12-digit Citizen Identity Card (CCCD)
_CCCD_12_RE = re.compile(
    r"\b\d{12}\b"
)

# 9-digit Identity Card (CMND) accompanied by keyword context
_CMND_9_RE = re.compile(
    r"(?i:\b(?:cmnd|cccd|cmt|can cuoc|so dinh danh)\b\s*[:#-]?\s*)\b\d{9}\b"
)

# Payment / Credit Card numbers (16 digits formatted or contiguous)
_CREDIT_CARD_RE = re.compile(
    r"\b(?:\d{4}[ -]?){3}\d{4}\b"
)

# API keys and bearer secrets (sk-..., api_key_..., etc.)
_API_SECRET_RE = re.compile(
    r"\b(?:sk|key|token|api_key|bearer)[-_A-Za-z0-9]{16,}\b",
    re.IGNORECASE,
)

_REDACTION_MAP: Tuple[Tuple[Pattern[str], str], ...] = (
    (_API_SECRET_RE, "[REDACTED_SECRET]"),
    (_CREDIT_CARD_RE, "[REDACTED_CARD]"),
    (_EMAIL_RE, "[REDACTED_EMAIL]"),
    (_PHONE_RE, "[REDACTED_PHONE]"),
    (_CMND_9_RE, "[REDACTED_ID]"),
    (_CCCD_12_RE, "[REDACTED_ID]"),
)


def has_pii(text: str) -> bool:
    """Return True if text contains recognizable PII or secret tokens."""
    if not text or not isinstance(text, str):
        return False
    return any(pattern.search(text) is not None for pattern, _ in _REDACTION_MAP)


def mask_pii(text: str) -> str:
    """Mask PII tokens with safe redaction placeholders."""
    if not text or not isinstance(text, str):
        return ""
    result = text
    for pattern, placeholder in _REDACTION_MAP:
        result = pattern.sub(placeholder, result)
    return result


def detect_pii_entities(text: str) -> List[Dict[str, str]]:
    """Return structured list of detected PII entities without logging their raw secrets."""
    if not text or not isinstance(text, str):
        return []
    findings: List[Dict[str, str]] = []
    category_map = [
        (_API_SECRET_RE, "secret_key"),
        (_CREDIT_CARD_RE, "credit_card"),
        (_EMAIL_RE, "email"),
        (_PHONE_RE, "phone_number"),
        (_CMND_9_RE, "national_id"),
        (_CCCD_12_RE, "national_id"),
    ]
    for pattern, category in category_map:
        for match in pattern.finditer(text):
            findings.append({
                "category": category,
                "span_start": str(match.start()),
                "span_end": str(match.end()),
            })
    return findings

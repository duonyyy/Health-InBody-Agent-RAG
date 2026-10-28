"""Input sanitizer and PII redactor (CCCD, Phone, Email) per Decree 13/2023/ND-CP."""

import re

PHONE_REGEX = re.compile(r"(?:\+84|0)(?:3[2-9]|5[6|8|9]|7[0|6-9]|8[1-5]|9[0-9])[0-9]{7}\b")
CCCD_REGEX = re.compile(r"\b\d{12}\b")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


class InputSanitizer:
    """Sanitizes user queries and masks sensitive PII before LLM reasoning."""

    @staticmethod
    def sanitize(text: str) -> str:
        if not text:
            return ""
        # Strip potential null bytes and control characters
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        return cleaned.strip()

    @staticmethod
    def mask_pii(text: str) -> str:
        if not text:
            return ""
        masked = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
        masked = CCCD_REGEX.sub("[REDACTED_CCCD]", masked)
        masked = EMAIL_REGEX.sub("[REDACTED_EMAIL]", masked)
        return masked

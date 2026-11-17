"""Deterministic parsing/validation of explicit metrics, without IO or web types."""

import math
import re
import unicodedata
from typing import Optional


class InvalidHealthInput(ValueError):
    """Public-safe input error; never include the original health data."""


def normalize_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    without_marks = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", without_marks.replace("đ", "d")).strip()


# The boundary prevents searching again inside a signed or decimal number.
_NUMBER = r"(?<![\w.,+\-−])(?P<value>[+\-−]?\s*\d+(?:[.,]\d+)?)"
_CONNECTOR = r"\s*(?:la|=|:)?\s*"
_WEIGHT_UNIT = r"(?:kg|kilo|ky|can)\b"
_PBF_LABEL = r"(?:pbf|phan tram mo|ty le mo|ti le mo|body\s*fat|bf|mo co the)"
_VISCERAL_LABEL = r"(?:mo noi tang|visceral fat)"
_PATTERNS = {
    "weight_kg": [(_NUMBER + r"\s*" + _WEIGHT_UNIT, "kg"),
                  (r"(?:can nang|nang)" + _CONNECTOR + _NUMBER, "kg")],
    "height_cm": [
        (r"(?<![\w.,+\-−])(?P<value>[+\-−]?\s*\d+)\s*m\s*(?P<cm>\d{1,2})\b", "notation"),
        (_NUMBER + r"\s*cm\b", "cm"),
        (_NUMBER + r"\s*m\b", "m"),
        (r"(?:chieu cao|cao)" + _CONNECTOR + _NUMBER, "height")],
    "pbf_percent": [(_PBF_LABEL + _CONNECTOR + _NUMBER, "%"),
                    (_NUMBER + r"\s*%\s*(?:mo|fat|pbf)\b", "%")],
    "visceral_fat_level": [(_VISCERAL_LABEL + r"\s*(?:level|muc)?" + _CONNECTOR + _NUMBER, "level")],
}
_LABELS = {"weight_kg": "cân nặng", "height_cm": "chiều cao",
           "pbf_percent": "PBF", "visceral_fat_level": "mỡ nội tạng"}
_RANGES = {"weight_kg": (0, 500, False), "height_cm": (30, 300, True),
           "pbf_percent": (0, 100, True), "visceral_fat_level": (0, 100, True)}


def _is_change(text: str, start: int) -> bool:
    """A change/target amount is not a current absolute measurement."""
    prefix = text[max(0, start - 70):start]
    if re.search(
        r"(?:giam|tang)(?:\s+(?:can|mo|them|duoc|khoang|hon|gan|tu|toi|con|xuong|len|la))*\s*$",
        prefix,
    ):
        return True
    if re.search(r"(?:muc tieu|mong muon|du kien)(?:\s+(?:can nang|la|con|dat|toi|xuong|len))*\s*$", prefix):
        return True
    clause = re.split(r"[,;!?\n]", prefix)[-1]
    return bool(re.search(r"\b(?:truoc day|truoc kia|nam ngoai|thang truoc|tuan truoc|hom qua)\b", clause)
                and not re.search(r"\b(?:hien tai|bay gio|hom nay)\b", clause))


def extract_health_metric(text: str, field: str) -> Optional[float]:
    """Preserve signed values; refuse ambiguous values instead of choosing one."""
    text = normalize_match_text(text)
    # Ranges with a trailing unit must not be parsed as their upper endpoint.
    units = {"weight_kg": _WEIGHT_UNIT, "height_cm": r"(?:cm|m)\b",
             "pbf_percent": r"%", "visceral_fat_level": r"(?:level|muc)\b"}
    for match in re.finditer(r"\d+(?:[.,]\d+)?\s*(?:-|–|—|den|toi)\s*\d+(?:[.,]\d+)?\s*" + units[field], text):
        if not _is_change(text, match.start()):
            raise InvalidHealthInput(f"Vui lòng xác nhận một giá trị {_LABELS[field]} hiện tại.")
    values, spans = [], []
    for pattern, unit in _PATTERNS[field]:
        for match in re.finditer(pattern, text):
            start, end = match.span("value")
            if any(start < old_end and end > old_start for old_start, old_end in spans):
                continue
            if _is_change(text, match.start()):
                continue
            if re.match(r"\s*(?:-|–|—|den|toi)\s*\d", text[match.end():]):
                raise InvalidHealthInput(f"Vui lòng xác nhận một giá trị {_LABELS[field]} hiện tại.")
            raw = match.group("value").replace("−", "-").replace(" ", "").replace(",", ".")
            value = float(raw)
            if unit == "notation":
                cm = match.group("cm")
                value = (-1 if raw.startswith("-") else 1) * (abs(value) * 100 + int(cm) * (10 if len(cm) == 1 else 1))
            elif unit == "m" or (unit == "height" and 0 < abs(value) < 3):
                value *= 100
            values.append(value)
            spans.append(match.span())
    if len(set(values)) > 1:
        raise InvalidHealthInput(f"Vui lòng xác nhận một giá trị {_LABELS[field]} hiện tại.")
    return values[0] if values else None


def validate_health_input(question: str) -> None:
    """Reject explicit invalid metrics before context fallback or side effects."""
    for field, (lower, upper, inclusive) in _RANGES.items():
        value = extract_health_metric(question, field)
        if value is None:
            continue
        if not math.isfinite(value) or value > upper or (value < lower if inclusive else value <= lower):
            raise InvalidHealthInput(f"Giá trị {_LABELS[field]} không hợp lệ. Vui lòng kiểm tra dấu, đơn vị và nhập lại.")

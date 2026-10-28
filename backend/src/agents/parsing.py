"""Text parsing helpers shared by Health/InBody agents."""

import re
import unicodedata
from typing import List, Optional


def normalize_match_text(text: str) -> str:
    """Normalize Vietnamese text for deterministic matching while preserving words."""
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks.replace("đ", "d")).strip()


def extract_number_after_patterns(text: str, patterns: List[str]) -> Optional[float]:
    text_lower = (text or "").lower()
    normalized_text = normalize_match_text(text)
    for pattern in patterns:
        for candidate_text, candidate_pattern in [
            (text_lower, pattern),
            (normalized_text, normalize_match_text(pattern)),
        ]:
            match = re.search(candidate_pattern, candidate_text)
            if match:
                try:
                    return float(match.group(1).replace(",", "."))
                except ValueError:
                    continue
    return None


def extract_weight_kg(text: str) -> Optional[float]:
    return extract_number_after_patterns(
        text,
        [
            r"(\d+(?:[\.,]\d+)?)\s*(?:kg|kilo|ký|ky|cân|can)\b",
            r"(?:nặng|cân nặng)\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
        ],
    )


def extract_height_cm(text: str) -> Optional[float]:
    # 1. Handle Vietnamese "1m70", "1m7", "1m68", "1 m 75" format first
    m_pattern = re.search(
        r"(?:^|[^\w.,])([12])\s*m\s*(\d{1,2})\b",
        (text or "").lower(),
    )
    if m_pattern:
        m = int(m_pattern.group(1))
        cm_part = m_pattern.group(2)
        cm = int(cm_part) * 10 if len(cm_part) == 1 else int(cm_part)
        return float(m * 100 + cm)

    height = extract_number_after_patterns(
        text,
        [
            r"(\d+(?:[\.,]\d+)?)\s*cm\b",
            r"(?:cao|chiều cao)\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"(\d(?:[\.,]\d+)?)\s*m\b",
        ],
    )
    if height and height < 3:
        return height * 100
    return height


def extract_pbf(text: str) -> Optional[float]:
    return extract_number_after_patterns(
        text,
        [
            r"(?:pbf|phần trăm mỡ|phan tram mo|tỷ lệ mỡ|ty le mo|ti le mo|body\s*fat|bf)\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"mỡ cơ thể\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"(\d+(?:[\.,]\d+)?)\s*%\s*(?:mỡ|fat|pbf)",
        ],
    )


def extract_visceral_fat(text: str) -> Optional[float]:
    return extract_number_after_patterns(
        text,
        [
            r"mỡ nội tạng\s*(?:level|mức|là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"visceral fat\s*(?:level|là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
        ],
    )


def extract_sex(text: str) -> Optional[str]:
    text_raw = (text or "").lower()
    norm = normalize_match_text(text)

    # 1. Check female first with word boundary
    if re.search(r"\b(nu|female|gioi\s*tinh\s*nu|nu\s*gioi)\b", norm):
        return "female"

    # 2. In Vietnamese, 'năm' (with ă) means year/five, NEVER male gender.
    # Clean out words with ă before normalization
    cleaned_raw = re.sub(r"\bn[ăắằẳẵặ]m\b", " ", text_raw)
    cleaned_norm = normalize_match_text(cleaned_raw)

    # Also clean unaccented time/number phrases: 'nam nay', 'nam ngoai', '\d+ nam', 'nam tuoi'
    cleaned_norm = re.sub(
        r"\b(nam\s*nay|nam\s*ngoai|nam\s*truoc|nam\s*sau|\d+\s*nam|nam\s*tuoi)\b",
        " ",
        cleaned_norm,
    )

    if re.search(r"\b(nam|male|gioi\s*tinh\s*nam|nam\s*gioi)\b", cleaned_norm):
        return "male"
    return None


def infer_goal(text: str) -> Optional[str]:
    text_lower = normalize_match_text(text)
    if any(k in text_lower for k in ["tang co", "tang can", "muscle", "hypertrophy"]):
        return "muscle_gain"
    if any(k in text_lower for k in ["giam mo", "giam can", "fat loss", "fat_loss", "weight loss"]):
        return "fat_loss"
    if any(k in text_lower for k in ["duy tri", "giu can", "maintenance"]):
        return "maintenance"
    return None


def infer_days_per_week(text: str) -> Optional[int]:
    match = re.search(
        r"(\d+)\s*(?:buoi|ngay)\s*(?:/|moi|1|mot)?\s*(?:tuan|week)",
        normalize_match_text(text),
    )
    if match:
        return max(1, min(7, int(match.group(1))))
    return None

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
            r"(\d+(?:[\.,]\d+)?)\s*kg",
            r"nặng\s*(\d+(?:[\.,]\d+)?)",
            r"cân nặng\s*(\d+(?:[\.,]\d+)?)",
        ],
    )


def extract_height_cm(text: str) -> Optional[float]:
    height = extract_number_after_patterns(
        text,
        [
            r"(\d+(?:[\.,]\d+)?)\s*cm",
            r"cao\s*(\d+(?:[\.,]\d+)?)",
            r"chiều cao\s*(\d+(?:[\.,]\d+)?)",
            r"(\d(?:[\.,]\d+)?)\s*m",
        ],
    )
    if height and height < 3:
        return height * 100
    return height


def extract_pbf(text: str) -> Optional[float]:
    return extract_number_after_patterns(
        text,
        [
            r"pbf\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"phần trăm mỡ\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"mỡ cơ thể\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)\s*%",
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
    text_lower = f" {normalize_match_text(text)} "
    if any(keyword in text_lower for keyword in [" nam ", "gioi tinh nam", " male "]):
        return "male"
    if any(keyword in text_lower for keyword in [" nu ", "gioi tinh nu", " female "]):
        return "female"
    return None


def infer_goal(text: str) -> str:
    text_lower = normalize_match_text(text)
    if "tang co" in text_lower or "muscle" in text_lower:
        return "muscle_gain"
    if "duy tri" in text_lower or "maintenance" in text_lower:
        return "maintenance"
    return "fat_loss"


def infer_days_per_week(text: str) -> int:
    match = re.search(
        r"(\d+)\s*(?:buoi|ngay)\s*/?\s*(?:tuan|week)",
        normalize_match_text(text),
    )
    if match:
        return max(1, min(7, int(match.group(1))))
    return 3

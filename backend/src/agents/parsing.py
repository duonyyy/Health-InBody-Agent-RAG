"""Text parsing helpers shared by Health/InBody agents."""

import re
from typing import List, Optional

from health.validation import extract_health_metric, normalize_match_text


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
    return extract_health_metric(text, "weight_kg")


def extract_height_cm(text: str) -> Optional[float]:
    return extract_health_metric(text, "height_cm")


def extract_pbf(text: str) -> Optional[float]:
    return extract_health_metric(text, "pbf_percent")


def extract_visceral_fat(text: str) -> Optional[float]:
    return extract_health_metric(text, "visceral_fat_level")


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

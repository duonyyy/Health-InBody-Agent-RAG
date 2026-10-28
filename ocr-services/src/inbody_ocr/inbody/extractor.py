"""InBody image extraction with deterministic validation and review signals."""

import logging
import math
import re
from typing import Any

from inbody_ocr.inbody.prompts import INBODY_OCR_PROMPT
from inbody_ocr.inbody.schemas import ExtractedField, InBodyResponse
from inbody_ocr.clients.ollama import OllamaClient
from inbody_ocr.imaging.preprocess import PreparedImage
from inbody_ocr.common.json import JsonExtractionError, extract_json_object

logger = logging.getLogger(__name__)

# These limits match the measurement API. Values outside them need manual review.
FIELD_LIMITS = {
    "height_cm": (50.0, 250.0),
    "weight_kg": (20.0, 400.0),
    "smm_kg": (0.0, 200.0),
    "bfm_kg": (0.0, 250.0),
    "pbf_percent": (0.0, 80.0),
    "visceral_fat_level": (0.0, 50.0),
    "body_water_l": (0.0, 200.0),
}


class InBodyOcrService:
    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def extract(self, images: list[PreparedImage]) -> InBodyResponse:
        fields: dict[str, ExtractedField] = {}
        warnings: list[str] = []
        conflicted: set[str] = set()
        for image in images:
            output = self.client.generate(
                prompt=INBODY_OCR_PROMPT,
                image_base64=image.image_base64,
                num_predict=self.client.settings.ocr_num_predict,
            )
            try:
                payload = extract_json_object(output)
            except JsonExtractionError:
                warnings.append(f"Trang {image.page_number}: không đọc được JSON; cần nhập tay.")
                continue
            for name, limits in FIELD_LIMITS.items():
                item = payload.get(name)
                parsed = _validated_field(item, image.page_number, limits)
                if parsed is None:
                    if item is not None and item != {"value": None, "raw_text": ""}:
                        warnings.append(f"Trang {image.page_number}: {name} cần kiểm tra thủ công.")
                    continue
                if name in conflicted:
                    continue
                if name in fields and fields[name].value != parsed.value:
                    warnings.append(f"{name} khác nhau giữa các trang; cần kiểm tra thủ công.")
                    fields.pop(name, None)
                    conflicted.add(name)
                    continue
                fields[name] = parsed
        return InBodyResponse(
            extracted_fields=fields,
            unresolved_fields=[name for name in FIELD_LIMITS if name not in fields],
            warnings=list(dict.fromkeys(warnings)),
        )


def _validated_field(
    item: Any, page_number: int, limits: tuple[float, float]
) -> ExtractedField | None:
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    raw = item.get("raw_text")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > 80:
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not limits[0] <= numeric <= limits[1]:
        return None
    visible_numbers = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
    if len(visible_numbers) != 1:
        return None
    visible = float(visible_numbers[0].replace(",", "."))
    if abs(visible - numeric) > 0.05:
        return None
    return ExtractedField(value=numeric, raw_text=raw.strip(), page_number=page_number)

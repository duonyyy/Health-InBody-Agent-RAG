"""InBody extraction service combining PaddleOCR text scanning with LLM structuring."""

import logging
import math
import re
from typing import Any

from inbody_ocr.clients.ollama import OllamaClient
from inbody_ocr.clients.paddle import PaddleOcrError, PaddleOcrReader
from inbody_ocr.common.json import JsonExtractionError, extract_json_object
from inbody_ocr.imaging.layout import to_plain_text
from inbody_ocr.imaging.preprocess import PreparedImage
from inbody_ocr.inbody.prompts import INBODY_TEXT_EXTRACTION_PROMPT
from inbody_ocr.inbody.schemas import ExtractedField, InBodyResponse

logger = logging.getLogger(__name__)

# Medical range limits matching measurement persistence contract
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
    def __init__(
        self,
        paddle: PaddleOcrReader,
        llm: OllamaClient,
        row_gap_px: int = 12,
    ) -> None:
        self.paddle = paddle
        self.llm = llm
        self.row_gap_px = row_gap_px

    def extract(self, images: list[PreparedImage]) -> InBodyResponse:
        fields: dict[str, ExtractedField] = {}
        warnings: list[str] = []
        conflicted: set[str] = set()

        for image in images:
            # Stage 1: PaddleOCR text detection & recognition
            try:
                ocr_lines = self.paddle.read(image.raw_bytes)
            except PaddleOcrError as exc:
                logger.warning("PaddleOCR error on page %s: %s", image.page_number, exc)
                warnings.append(f"Trang {image.page_number}: không quét được chữ; cần nhập tay.")
                continue

            if not ocr_lines:
                warnings.append(f"Trang {image.page_number}: không phát hiện chữ trên ảnh; cần nhập tay.")
                continue

            # Stage 2: Spatial layout formatting
            plain_text = to_plain_text(ocr_lines, row_gap_px=self.row_gap_px)

            # Stage 3: LLM structuring (Text only, no vision input needed)
            prompt = INBODY_TEXT_EXTRACTION_PROMPT.format(ocr_text=plain_text)
            output = self.llm.generate(
                prompt=prompt,
                format_json=True,
                num_predict=self.llm.settings.ocr_num_predict,
            )

            # Stage 4: Parse & Deterministic validation
            try:
                payload = extract_json_object(output)
            except JsonExtractionError:
                warnings.append(f"Trang {image.page_number}: không đọc được JSON từ LLM; cần nhập tay.")
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
    item: Any,
    page_number: int,
    limits: tuple[float, float],
    confidence: float | None = None,
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
    return ExtractedField(
        value=numeric,
        raw_text=raw.strip(),
        page_number=page_number,
        confidence=confidence,
    )

"""PaddleOCR client for fast, deterministic text and coordinate extraction."""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    bbox: list[list[float]]

    @property
    def top_y(self) -> float:
        if not self.bbox:
            return 0.0
        return min(point[1] for point in self.bbox)

    @property
    def left_x(self) -> float:
        if not self.bbox:
            return 0.0
        return min(point[0] for point in self.bbox)


class PaddleOcrError(RuntimeError):
    """Raised when PaddleOCR fails to initialize or process an image."""


class PaddleOcrReader:
    """Reader wrapping PaddleOCR. Reused across requests."""

    def __init__(
        self,
        lang: str = "ch",
        use_gpu: bool = False,
        min_confidence: float = 0.5,
        engine: Any = None,
    ) -> None:
        self.lang = lang
        self.use_gpu = use_gpu
        self.min_confidence = min_confidence
        self._engine = engine

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR  # type: ignore[import]

                self._engine = PaddleOCR(
                    lang=self.lang,
                    use_angle_cls=True,
                    use_gpu=self.use_gpu,
                    show_log=False,
                )
            except Exception as exc:
                raise PaddleOcrError(f"Không thể khởi tạo PaddleOCR engine: {exc}") from exc
        return self._engine

    def is_available(self) -> bool:
        try:
            self._get_engine()
            return True
        except Exception:
            return False

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        """Perform text detection and recognition on raw image bytes."""
        import numpy as np

        if not image_bytes:
            return []

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_np = np.array(image)
        except Exception as exc:
            raise PaddleOcrError(f"Không thể đọc ảnh để OCR: {exc}") from exc

        engine = self._get_engine()
        try:
            result = engine.ocr(img_np, cls=True)
        except Exception as exc:
            raise PaddleOcrError(f"PaddleOCR scan thất bại: {exc}") from exc

        lines: list[OcrLine] = []
        for page in (result or []):
            if not page:
                continue
            for item in page:
                if not item or len(item) < 2:
                    continue
                bbox, text_score = item[0], item[1]
                if not isinstance(text_score, (list, tuple)) or len(text_score) < 2:
                    continue
                text, score = str(text_score[0]).strip(), float(text_score[1])
                if text and score >= self.min_confidence:
                    lines.append(
                        OcrLine(
                            text=text,
                            confidence=score,
                            bbox=[[float(p[0]), float(p[1])] for p in bbox],
                        )
                    )

        return lines

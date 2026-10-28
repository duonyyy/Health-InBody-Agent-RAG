"""Clients package for InBody OCR."""

from inbody_ocr.clients.ollama import (
    OllamaClient,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from inbody_ocr.clients.paddle import (
    OcrLine,
    PaddleOcrError,
    PaddleOcrReader,
)

__all__ = [
    "OllamaClient",
    "OllamaError",
    "OllamaModelNotFoundError",
    "OllamaTimeoutError",
    "OcrLine",
    "PaddleOcrError",
    "PaddleOcrReader",
]

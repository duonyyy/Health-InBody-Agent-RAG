"""Shared dependency providers for InBody OCR Paddle Service."""

from inbody_ocr.clients.ollama import OllamaClient
from inbody_ocr.clients.paddle import PaddleOcrReader
from inbody_ocr.config import get_settings
from inbody_ocr.inbody.extractor import InBodyOcrService

_ollama_client: OllamaClient | None = None
_paddle_reader: PaddleOcrReader | None = None


def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(get_settings())
    return _ollama_client


def get_paddle_reader() -> PaddleOcrReader:
    global _paddle_reader
    if _paddle_reader is None:
        settings = get_settings()
        _paddle_reader = PaddleOcrReader(
            lang=settings.paddle_lang,
            use_gpu=settings.paddle_use_gpu,
            min_confidence=settings.paddle_min_confidence,
        )
    return _paddle_reader


def get_inbody_service() -> InBodyOcrService:
    settings = get_settings()
    return InBodyOcrService(
        paddle=get_paddle_reader(),
        llm=get_ollama_client(),
        row_gap_px=settings.paddle_row_gap_px,
    )

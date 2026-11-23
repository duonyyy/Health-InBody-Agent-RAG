"""Shared dependency providers for InBody OCR Paddle Service."""

import hmac
from fastapi import Depends, Header, HTTPException, Request, status

from inbody_ocr.clients.ollama import OllamaClient
from inbody_ocr.clients.paddle import PaddleOcrReader
from inbody_ocr.config import Settings, get_settings
from inbody_ocr.inbody.extractor import InBodyOcrService

_ollama_client: OllamaClient | None = None
_paddle_reader: PaddleOcrReader | None = None


def verify_service_api_key(
    request: Request,
    settings: Settings = Depends(get_settings),
    x_internal_service_key: str | None = Header(default=None, alias="X-Internal-Service-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Xác thực internal service key giữa chatbot backend và OCR service."""
    configured_key = settings.internal_service_key
    if not configured_key:
        return

    provided_key = x_internal_service_key
    if not provided_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_key = parts[1]

    if not provided_key or not hmac.compare_digest(provided_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Xác thực dịch vụ nội bộ thất bại.",
            headers={"WWW-Authenticate": "Bearer"},
        )


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

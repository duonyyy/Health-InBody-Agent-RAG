"""Environment configuration for the internal InBody OCR worker."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    ollama_url: str = "http://host.docker.internal:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: int = Field(default=45, ge=1, le=180)
    health_cache_seconds: int = Field(default=30, ge=0)
    ocr_num_predict: int = Field(default=800, ge=100, le=4096)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_pdf_pages: int = Field(default=2, ge=1, le=10)
    pdf_dpi: int = Field(default=180, ge=72, le=300)
    max_image_side: int = Field(default=1800, ge=512, le=4096)

    @property
    def ollama_base_url(self) -> str:
        return self.ollama_url.rstrip("/")

    @property
    def ollama_generate_url(self) -> str:
        return f"{self.ollama_base_url}/api/generate"

    @property
    def ollama_chat_url(self) -> str:
        return f"{self.ollama_base_url}/api/chat"


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        ollama_url=os.getenv("OLLAMA_URL") or os.getenv("OCR_OLLAMA_URL", "http://host.docker.internal:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL") or os.getenv("OCR_OLLAMA_MODEL", ""),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS") or os.getenv("OCR_OLLAMA_TIMEOUT_SECONDS", "45")),
        health_cache_seconds=int(os.getenv("HEALTH_CACHE_SECONDS", "30")),
        ocr_num_predict=int(os.getenv("OCR_NUM_PREDICT", "800")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "2")),
        pdf_dpi=int(os.getenv("PDF_DPI", "180")),
        max_image_side=int(os.getenv("MAX_IMAGE_SIDE", "1800")),
    )


def _load_dotenv() -> None:
    # Compose injects environment variables; local runs read .env from the service working directory.
    path = Path.cwd() / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#") and "=" in text:
            key, value = text.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

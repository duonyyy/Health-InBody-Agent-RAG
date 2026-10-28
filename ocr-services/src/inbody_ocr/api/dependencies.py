"""Shared HTTP clients; no health data is retained between requests."""

from inbody_ocr.config import get_settings
from inbody_ocr.inbody.extractor import InBodyOcrService
from inbody_ocr.clients.ollama import OllamaClient

client = OllamaClient(get_settings())


def get_ollama_client() -> OllamaClient:
    return client


def get_inbody_service() -> InBodyOcrService:
    return InBodyOcrService(OllamaClient(get_settings()))

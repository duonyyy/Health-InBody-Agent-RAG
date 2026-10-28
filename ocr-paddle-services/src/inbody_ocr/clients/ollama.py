"""Ollama client for text-based information extraction."""

import logging
import time
from typing import Any

import requests

from inbody_ocr.config import Settings

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Base exception for Ollama client failures."""


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama does not respond within the configured timeout."""


class OllamaModelNotFoundError(OllamaError):
    """Raised when the configured model is not available."""


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        # Health requests must go only to the configured Ollama URL, not HTTP_PROXY.
        self.session.trust_env = False
        self._health_cached_at = 0.0
        self._health_cache: tuple[bool, bool, str] | None = None

    def health(self) -> tuple[bool, bool, str]:
        now = time.monotonic()
        if self._health_cache and now - self._health_cached_at < self.settings.health_cache_seconds:
            return self._health_cache

        try:
            response = self.session.get(
                f"{self.settings.ollama_base_url}/api/tags",
                timeout=min(10, self.settings.ollama_timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return False, False, str(exc)
        except ValueError as exc:
            logger.warning("Ollama health check returned invalid JSON: %s", exc)
            return True, False, "Ollama /api/tags returned invalid JSON"

        models = payload.get("models", [])
        model_names: set[str] = set()
        for model in models:
            if not isinstance(model, dict):
                continue
            for key in ("name", "model"):
                value = model.get(key)
                if isinstance(value, str) and value:
                    model_names.add(value)
        model_available = bool(self.settings.ollama_model and self.settings.ollama_model in model_names)
        detail = "ok" if model_available else f"Model {self.settings.ollama_model} not found"
        self._health_cache = (True, model_available, detail)
        self._health_cached_at = now
        return self._health_cache

    def assert_model_available(self) -> None:
        reachable, model_available, detail = self.health()
        if not reachable:
            raise OllamaError(f"Ollama is not reachable: {detail}")
        if not model_available:
            raise OllamaModelNotFoundError(detail)

    def generate(
        self,
        prompt: str,
        format_json: bool = False,
        num_predict: int | None = None,
    ) -> str:
        effective_num_predict = num_predict or self.settings.ocr_num_predict
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "top_p": 0.2,
                "num_predict": effective_num_predict,
                "repeat_last_n": 128,
                "repeat_penalty": 1.25,
            },
        }
        if format_json:
            payload["format"] = "json"

        try:
            response = self.session.post(
                self.settings.ollama_generate_url,
                json=payload,
                timeout=self.settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            logger.warning("Ollama generate timeout")
            raise OllamaTimeoutError("Ollama request timed out") from exc
        except requests.RequestException as exc:
            logger.warning("Ollama generate request failed: %s", exc)
            raise OllamaError(f"Ollama request failed: {exc}") from exc
        except ValueError as exc:
            logger.warning("Ollama generate returned invalid JSON")
            raise OllamaError("Ollama returned invalid JSON response") from exc

        text = extract_text_response(data)
        if not isinstance(text, str):
            logger.warning("Ollama response keys without text: %s", sorted(data.keys()))
            raise OllamaError("Ollama response does not contain a text response")
        return text


def extract_text_response(data: dict[str, Any]) -> str | None:
    response = data.get("response")
    if isinstance(response, str):
        return response

    message = data.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    output = data.get("output")
    if isinstance(output, str):
        return output

    return None

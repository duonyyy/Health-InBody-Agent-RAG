"""Reusable HTTP client sessions with connection pooling.

Avoids per-request TCP handshakes and ephemeral port exhaustion for internal
services such as Ollama, custom LLM APIs, and InBody OCR.
"""

import os
import threading
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

_lock = threading.Lock()
_llm_session: Optional[requests.Session] = None
_ocr_session: Optional[requests.Session] = None


def create_pooled_session(
    pool_connections: int = 10,
    pool_maxsize: int = 20,
    max_retries: int = 0,
    trust_env: bool = False,
) -> requests.Session:
    """Create a new requests.Session configured with an HTTPAdapter connection pool."""
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=max_retries,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.trust_env = trust_env
    return session


def get_shared_llm_session() -> requests.Session:
    """Return the shared pooled HTTP session for LLM API calls (Ollama / custom API)."""
    global _llm_session
    if _llm_session is None:
        with _lock:
            if _llm_session is None:
                pool_connections = int(os.getenv("LLM_POOL_CONNECTIONS", "10"))
                pool_maxsize = int(os.getenv("LLM_POOL_MAXSIZE", "20"))
                _llm_session = create_pooled_session(
                    pool_connections=pool_connections,
                    pool_maxsize=pool_maxsize,
                    max_retries=0,
                    trust_env=False,
                )
    return _llm_session


def get_shared_ocr_session() -> requests.Session:
    """Return the shared pooled HTTP session for OCR service calls."""
    global _ocr_session
    if _ocr_session is None:
        with _lock:
            if _ocr_session is None:
                pool_connections = int(os.getenv("OCR_POOL_CONNECTIONS", "5"))
                pool_maxsize = int(os.getenv("OCR_POOL_MAXSIZE", "10"))
                _ocr_session = create_pooled_session(
                    pool_connections=pool_connections,
                    pool_maxsize=pool_maxsize,
                    max_retries=0,
                    trust_env=False,
                )
    return _ocr_session


def close_http_sessions() -> None:
    """Close and reset all shared HTTP sessions.

    Safe to call during application shutdown or test teardown.
    """
    global _llm_session, _ocr_session
    with _lock:
        if _llm_session is not None:
            try:
                _llm_session.close()
            except Exception:
                pass
            _llm_session = None

        if _ocr_session is not None:
            try:
                _ocr_session.close()
            except Exception:
                pass
            _ocr_session = None

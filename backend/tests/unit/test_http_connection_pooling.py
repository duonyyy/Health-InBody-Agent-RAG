"""Unit tests for reusable HTTP Client Session with Connection Pooling.

Verifies:
- requests.Session singleton reuse across requests.
- HTTPAdapter connection pool configuration (pool_connections, pool_maxsize, max_retries).
- Docker network proxy bypass (trust_env = False).
- Clean lifecycle shutdown (close_http_sessions).
- Fast integration with LLM client and OCR endpoint.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from requests.adapters import HTTPAdapter

from api.inbody_ocr import extract_inbody, get_ocr_http_session, get_ocr_session_provider, router as ocr_router
from auth.context import CurrentUser, get_current_user
from core.http_client import (
    close_http_sessions,
    create_pooled_session,
    get_shared_llm_session,
    get_shared_ocr_session,
)
from llm import client as llm_client


@pytest.fixture(autouse=True)
def _cleanup_sessions():
    """Ensure sessions are cleaned up before and after each test."""
    close_http_sessions()
    yield
    close_http_sessions()


def test_create_pooled_session_configuration():
    session = create_pooled_session(
        pool_connections=15,
        pool_maxsize=30,
        max_retries=0,
        trust_env=False,
    )
    try:
        assert session.trust_env is False
        http_adapter = session.adapters.get("http://")
        https_adapter = session.adapters.get("https://")
        assert isinstance(http_adapter, HTTPAdapter)
        assert isinstance(https_adapter, HTTPAdapter)
        assert http_adapter._pool_connections == 15
        assert http_adapter._pool_maxsize == 30
    finally:
        session.close()


def test_llm_session_singleton_and_pooling():
    session1 = get_shared_llm_session()
    session2 = get_shared_llm_session()
    # Must be the exact same session instance (connection reuse)
    assert session1 is session2
    assert session1.trust_env is False

    adapter = session1.adapters.get("http://")
    assert isinstance(adapter, HTTPAdapter)
    assert adapter._pool_connections >= 10
    assert adapter._pool_maxsize >= 20


def test_ocr_session_singleton_and_pooling():
    session1 = get_shared_ocr_session()
    session2 = get_shared_ocr_session()
    # Must be the exact same session instance (connection reuse)
    assert session1 is session2
    assert session1.trust_env is False

    adapter = session1.adapters.get("http://")
    assert isinstance(adapter, HTTPAdapter)
    assert adapter._pool_connections >= 5
    assert adapter._pool_maxsize >= 10


def test_close_http_sessions_resets_singletons():
    session_llm = get_shared_llm_session()
    session_ocr = get_shared_ocr_session()

    close_http_sessions()

    # Next call must create new sessions
    session_llm_new = get_shared_llm_session()
    session_ocr_new = get_shared_ocr_session()

    assert session_llm_new is not session_llm
    assert session_ocr_new is not session_ocr


def test_llm_client_uses_pooled_session(monkeypatch):
    """When requests.post is not monkeypatched, llm_client routes calls through pooled session."""
    pooled_session = get_shared_llm_session()
    fake_resp = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"message": {"content": "pooled response"}},
    )

    mock_post = MagicMock(return_value=fake_resp)
    monkeypatch.setattr(pooled_session, "post", mock_post)

    result = llm_client._chat_with_ollama(
        [{"role": "user", "content": "hello"}],
        model="pooled-model",
        think=False,
        timeout=5.0,
    )

    assert result == "pooled response"
    assert mock_post.called
    call_args, call_kwargs = mock_post.call_args
    assert "api/chat" in call_args[0]
    assert call_kwargs["json"]["model"] == "pooled-model"


def test_ocr_endpoint_uses_reusable_session(monkeypatch):
    """OCR endpoint calls the pooled session instead of creating & closing a new TCP session per request."""
    monkeypatch.setenv("FEATURE_OCR_UPLOAD", "true")
    monkeypatch.setattr("api.inbody_ocr._has_health_consent", lambda _subject: True)

    pooled_session = get_shared_ocr_session()
    fake_resp = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "document_type": "inbody_result",
            "parser_version": "inbody-v1",
            "status": "needs_confirmation",
            "extracted_fields": {},
            "unresolved_fields": [],
            "warnings": [],
        },
    )
    mock_post = MagicMock(return_value=fake_resp)
    monkeypatch.setattr(pooled_session, "post", mock_post)

    app = FastAPI()
    app.include_router(ocr_router)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("test-user")

    client = TestClient(app)
    response = client.post("/me/inbody-ocr", files={"file": ("report.png", b"filedata")})

    assert response.status_code == 200
    assert mock_post.called
    call_args, call_kwargs = mock_post.call_args
    assert call_args[0].endswith("/ocr/inbody")
    assert call_kwargs["files"]["file"][1] == b"filedata"


def test_ocr_endpoint_dependency_injection_override(monkeypatch):
    """OCR session provider can be overridden via FastAPI dependency injection."""
    monkeypatch.setenv("FEATURE_OCR_UPLOAD", "true")
    monkeypatch.setattr("api.inbody_ocr._has_health_consent", lambda _subject: True)

    fake_session = MagicMock()
    fake_session.post.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "document_type": "inbody_result",
            "parser_version": "inbody-v1",
            "status": "needs_confirmation",
            "extracted_fields": {},
            "unresolved_fields": [],
            "warnings": [],
        },
    )

    app = FastAPI()
    app.include_router(ocr_router)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("test-user")
    app.dependency_overrides[get_ocr_session_provider] = lambda: (lambda: fake_session)

    client = TestClient(app)
    response = client.post("/me/inbody-ocr", files={"file": ("report.png", b"custom-di")})

    assert response.status_code == 200
    assert fake_session.post.called

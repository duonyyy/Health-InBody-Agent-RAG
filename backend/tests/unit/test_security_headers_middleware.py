"""Tests for SecurityHeadersMiddleware and ContentLengthLimitMiddleware."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.security_middleware import ContentLengthLimitMiddleware, SecurityHeadersMiddleware


@pytest.fixture
def secure_app():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ContentLengthLimitMiddleware, default_max_bytes=1024, upload_max_bytes=4096)

    @app.get("/hello")
    def hello():
        return {"message": "hello"}

    @app.post("/submit")
    def submit(data: dict):
        return {"received": data}

    @app.post("/me/inbody-ocr")
    def upload_ocr(request: Request):
        return {"status": "ok"}

    @app.get("/docs")
    def docs():
        return "<html>docs</html>"

    return app


def test_security_headers_present(secure_app):
    client = TestClient(secure_app)
    response = client.get("/hello")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"
    assert headers.get("x-xss-protection") == "0"
    assert headers.get("content-security-policy") == "default-src 'none'; frame-ancestors 'none'"


def test_hsts_header_when_enabled(monkeypatch, secure_app):
    monkeypatch.setenv("ENABLE_HSTS", "true")
    client = TestClient(secure_app)
    response = client.get("/hello")
    assert response.headers.get("strict-transport-security") == "max-age=63072000; includeSubDomains"


def test_docs_content_security_policy(secure_app):
    client = TestClient(secure_app)
    response = client.get("/docs")
    assert "cdn.jsdelivr.net" in response.headers.get("content-security-policy", "")


def test_content_length_limit_exceeded(secure_app):
    client = TestClient(secure_app)
    large_payload = {"key": "x" * 2000}
    response = client.post("/submit", json=large_payload)
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_content_length_limit_allowed_for_ocr(secure_app):
    client = TestClient(secure_app)
    payload = {"data": "x" * 2000}
    response = client.post("/me/inbody-ocr", json=payload)
    assert response.status_code == 200

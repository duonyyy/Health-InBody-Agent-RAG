"""HTTP boundary tests that do not require a live PostgreSQL instance."""

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from api import personalization
from persistence import personalization_service as service


def test_removed_external_memory_routes_return_404(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    client = _client()
    headers = {"X-Dev-User-Id": "user-a"}
    assert client.put(
        "/me/memory-consent",
        json={"acknowledged_external_processing": True},
        headers=headers,
    ).status_code == 404
    assert client.delete("/me/memory", headers=headers).status_code == 404
    assert client.post("/me/memory/sync", headers=headers).status_code == 404


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(personalization.router)
    return TestClient(app)


def test_me_requires_authentication_in_production(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "production")
    response = _client().get("/me/profile", headers={"X-Dev-User-Id": "user-a"})
    assert response.status_code == 401


def test_me_uses_authenticated_subject_not_request_data(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    captured = []

    def fake_get_profile(subject):
        captured.append(subject)
        return {"display_name": "A"}

    monkeypatch.setattr(personalization.service, "get_profile", fake_get_profile)
    response = _client().get("/me/profile", headers={"X-Dev-User-Id": "user-a"})

    assert response.status_code == 200
    assert captured == ["user-a"]
    assert "user_id" not in response.json()


def test_personalization_debug_is_dev_only_and_redacted(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ENABLE_PERSONALIZATION_DEBUG", "false")
    response = _client().get(
        "/me/personalization-context",
        headers={"X-Dev-User-Id": "user-a"},
    )
    assert response.status_code == 404

    monkeypatch.setenv("ENABLE_PERSONALIZATION_DEBUG", "true")
    monkeypatch.setattr(
        personalization.service,
        "redacted_context",
        lambda subject: {"available": True, "profile": {"medical_conditions": {"count": 1}}},
    )
    response = _client().get(
        "/me/personalization-context",
        headers={"X-Dev-User-Id": "user-a"},
    )
    assert response.status_code == 200
    assert response.json()["profile"]["medical_conditions"] == {"count": 1}


def test_context_degrades_without_exposing_exception(monkeypatch):
    def fail(_subject):
        raise RuntimeError("database-secret-detail")

    monkeypatch.setattr(service, "build_confirmed_personalization_context", fail)
    result = service.safe_build_confirmed_context("user-a")

    assert result == {
        "available": False,
        "reason": "personalization_temporarily_unavailable",
        "provenance": [],
    }
    assert "database-secret-detail" not in str(result)

"""HTTP boundary tests that do not require a live PostgreSQL instance."""

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from api import personalization
from persistence import personalization_service as service


def test_zep_opt_in_requires_trusted_identity_and_explicit_ack(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ZEP_ALLOW_DEV_IDENTITY", "false")
    calls = []
    monkeypatch.setattr(personalization.service, "grant_external_memory_consent", lambda subject: calls.append(subject) or {"enabled": True})
    client = _client()
    headers = {"X-Dev-User-Id": "user-a"}
    assert client.put("/me/memory-consent", json={"acknowledged_external_processing": True}, headers=headers).status_code == 403
    assert calls == []
    monkeypatch.setenv("ZEP_ALLOW_DEV_IDENTITY", "true")
    assert client.put("/me/memory-consent", json={"acknowledged_external_processing": False}, headers=headers).status_code == 422
    assert client.put("/me/memory-consent", json={"acknowledged_external_processing": True}, headers=headers).status_code == 200
    assert calls == ["user-a"]


def test_zep_revoke_disables_consent_before_remote_delete(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ZEP_ALLOW_DEV_IDENTITY", "true")
    events = []
    monkeypatch.setattr(personalization.service, "revoke_external_memory_consent", lambda subject: events.append("revoke") or {"deletion_pending": True})
    monkeypatch.setattr(personalization.memory_sync, "finish_deletion", lambda subject: events.append("delete"))
    response = _client().delete("/me/memory", headers={"X-Dev-User-Id": "user-a"})
    assert response.status_code == 204
    assert events == ["revoke", "delete"]


def test_zep_delete_failure_keeps_pending_state(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ZEP_ALLOW_DEV_IDENTITY", "true")
    monkeypatch.setattr(personalization.service, "revoke_external_memory_consent", lambda subject: {"deletion_pending": True})
    monkeypatch.setattr(personalization.memory_sync, "finish_deletion", lambda subject: (_ for _ in ()).throw(RuntimeError("private-provider-detail")))
    monkeypatch.setattr(personalization.service, "mark_external_memory_deleted", lambda subject: (_ for _ in ()).throw(AssertionError("must stay pending")))
    response = _client().delete("/me/memory", headers={"X-Dev-User-Id": "user-a"})
    assert response.status_code == 503
    assert "private-provider-detail" not in response.text


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

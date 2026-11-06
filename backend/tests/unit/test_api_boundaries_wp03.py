"""Public safety and readiness behavior at the FastAPI boundary."""

import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from api import app as api


def test_async_urgent_chat_bypasses_queue_and_storage(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    calls = []

    def urgent(question, subject, **kwargs):
        calls.append((question, subject))
        return {"content": "Hãy liên hệ cấp cứu.", "status": "ok", "fast_path": "urgent_safety"}

    monkeypatch.setattr(api, "run_chat", urgent)
    monkeypatch.setattr(api.memory_store, "create_task", lambda *a: (_ for _ in ()).throw(AssertionError("task storage")))
    monkeypatch.setattr(api.memory_store, "load_history", lambda *a: (_ for _ in ()).throw(AssertionError("history")))
    response = TestClient(api.app).post(
        "/chat/complete", headers={"X-Dev-User-Id": "alice"},
        json={"user_message": "Tôi đau ngực và khó thở", "sync_request": False},
    )
    assert response.status_code == 200
    assert response.json()["response"]["fast_path"] == "urgent_safety"
    assert calls == [("Tôi đau ngực và khó thở", "alice")]


def test_readiness_returns_503_on_dependency_failure(monkeypatch):
    monkeypatch.setattr(api, "_readiness_report", lambda: {
        "status": "degraded", "dependencies": {"postgres": False, "qdrant": True},
        "llm_provider": "not_checked",
    })
    response = TestClient(api.app).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["postgres"] is False

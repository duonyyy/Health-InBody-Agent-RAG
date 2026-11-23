"""Unit tests for FastAPI HTTP Boundary Dependency Injection.

Validates (python-common-patterns references/dependency-injection.md):
- Overriding dependencies cleanly via app.dependency_overrides without monkeypatching sys.modules.
- get_chat_runner, get_memory_store, get_async_result_cls, get_readiness_reporter.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import (
    get_async_result_cls,
    get_chat_runner,
    get_llm_handler,
    get_memory_store,
    get_rate_limit_checker,
    get_readiness_reporter,
)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Ensure app.dependency_overrides is clean and dev auth is enabled."""
    monkeypatch.setenv("AUTH_MODE", "development")
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_urgent_chat_uses_injected_chat_runner():
    called = []

    def fake_chat_runner(question, subject, **kwargs):
        called.append((question, subject))
        return {
            "role": "assistant",
            "content": "Emergency handled safely.",
            "status": "ok",
        }

    app.dependency_overrides[get_chat_runner] = lambda: fake_chat_runner
    client = TestClient(app)

    res = client.post(
        "/chat/complete",
        json={"user_message": "đau ngực dữ dội khó thở", "bot_id": "test-bot"},
        headers={"X-Dev-User-Id": "test-user"},
    )
    assert res.status_code == 200
    assert len(called) == 1
    assert called[0][0] == "đau ngực dữ dội khó thở"
    assert called[0][1] == "test-user"
    assert res.json()["response"]["content"] == "Emergency handled safely."


def test_poll_chat_complete_uses_injected_async_result_cls():
    class FakeAsyncResult:
        status = "SUCCESS"
        result = {"content": "Async processing complete"}

        def __init__(self, task_id):
            self.task_id = task_id

    fake_store = SimpleNamespace(
        require_task_owner=lambda subject, task_id, **kw: True,
    )

    app.dependency_overrides[get_async_result_cls] = lambda: FakeAsyncResult
    app.dependency_overrides[get_memory_store] = lambda: fake_store
    client = TestClient(app)

    res = client.get(
        "/chat/complete/12345678-1234-5678-1234-567812345678?wait=false",
        headers={"X-Dev-User-Id": "test-user"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["task_status"] == "SUCCESS"
    assert data["task_result"] == {"content": "Async processing complete"}


def test_readiness_health_uses_injected_reporter():
    called = []

    def fake_readiness_report(**kwargs):
        called.append(True)
        return {
            "status": "ready",
            "dependencies": {"postgres": True, "qdrant": True, "valkey": True, "embedding_api": True},
            "llm_provider": "ollama",
        }

    app.dependency_overrides[get_readiness_reporter] = lambda: fake_readiness_report
    client = TestClient(app)

    res = client.get("/health/ready")
    assert res.status_code == 200
    assert len(called) == 1
    assert res.json()["status"] == "ready"


def test_agent_answer_uses_injected_chat_runner():
    called = []

    def fake_chat_runner(question, subject, **kwargs):
        called.append((question, subject))
        return {
            "content": "Agent answer handled.",
            "status": "ok",
        }

    app.dependency_overrides[get_chat_runner] = lambda: fake_chat_runner
    client = TestClient(app)

    res = client.post(
        "/agent/answer",
        json={"question": "tôi bị đau ngực nôn nao khó thở"},
        headers={"X-Dev-User-Id": "test-user"},
    )
    assert res.status_code == 200
    assert len(called) == 1
    assert res.json()["answer"] == "Agent answer handled."

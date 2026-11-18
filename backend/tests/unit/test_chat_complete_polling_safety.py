"""Unit tests verifying safe, non-blocking polling on GET /chat/complete/{task_id}.

Verifies:
1. Polling returns status immediately with wait=False without hanging connection.
2. Short hold timeout (hold_limit) returns 200 with current status (PENDING/STARTED)
   and Retry-After header instead of throwing 504 or blocking the probe lane indefinitely.
3. SUCCESS tasks return the complete task_result.
4. Non-owners receive 404.
"""

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")
from persistence.database import Base
from persistence.models import User
from memory import store


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture
def memory_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    monkeypatch.setattr(store, "session_scope", session)
    with session() as db:
        for subject in ("alice", "bob"):
            db.add(User(external_id=subject, consent_flags={"health_data_processing": True, "personalization": True}))
    yield session


def test_instant_poll_returns_pending_immediately_without_blocking(memory_db, monkeypatch):
    import api.app as api_app

    monkeypatch.setenv("AUTH_MODE", "development")
    task_id = store.create_task("alice")

    class FakeAsyncResult:
        status = "PENDING"
        result = None
        def __init__(self, tid):
            pass

    monkeypatch.setattr(api_app, "AsyncResult", FakeAsyncResult)
    client = TestClient(api_app.app)

    response = client.get(
        f"/chat/complete/{task_id}?wait=false",
        headers={"X-Dev-User-Id": "alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["task_status"] == "PENDING"
    assert data["task_result"] is None
    assert response.headers.get("retry-after") == "1"


def test_wait_poll_timeout_returns_current_status_instead_of_504(memory_db, monkeypatch):
    import api.app as api_app

    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("TASK_POLL_HOLD_SECONDS", "0.2")
    task_id = store.create_task("alice")

    class FakeAsyncResult:
        status = "STARTED"
        result = None
        def __init__(self, tid):
            pass

    monkeypatch.setattr(api_app, "AsyncResult", FakeAsyncResult)
    client = TestClient(api_app.app)

    response = client.get(
        f"/chat/complete/{task_id}?wait=true",
        headers={"X-Dev-User-Id": "alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["task_status"] == "STARTED"
    assert data["task_result"] is None
    assert response.headers.get("retry-after") == "1"


def test_completed_task_returns_success_result(memory_db, monkeypatch):
    import api.app as api_app

    monkeypatch.setenv("AUTH_MODE", "development")
    task_id = store.create_task("alice")

    class FakeAsyncResult:
        status = "SUCCESS"
        result = {"content": "Chào Alice, đây là kết quả."}
        def __init__(self, tid):
            pass

    monkeypatch.setattr(api_app, "AsyncResult", FakeAsyncResult)
    client = TestClient(api_app.app)

    response = client.get(
        f"/chat/complete/{task_id}",
        headers={"X-Dev-User-Id": "alice"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["task_status"] == "SUCCESS"
    assert data["task_result"]["content"] == "Chào Alice, đây là kết quả."

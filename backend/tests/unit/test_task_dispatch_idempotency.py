"""Unit tests for Task Dispatch Cleanup & Worker Idempotency Guard.

Validates (references/messaging-patterns.md):
1. Two-step dispatch cleanup: When llm_handler.apply_async fails, the orphaned
   ChatTask record in PostgreSQL is cleanly deleted.
2. Worker idempotency guard: When Celery redelivers a completed task (at-least-once delivery),
   llm_handle_message skips running the expensive LangGraph pipeline and returns
   the cached result immediately.
3. Task failure tracking: Unhandled exceptions during execution mark the task status as 'failed'.
"""

import asyncio
import os
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


from persistence.database import Base
from persistence.models import User
from persistence import personalization_service as profiles
from memory import store
from memory.models import ChatTask
from services.chat_service import ChatService, QueueUnavailableError
from jobs.tasks import llm_handle_message


@pytest.fixture
def memory_db(monkeypatch):
    """Provides isolated SQLite DB for real ORM task testing."""
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
    monkeypatch.setattr(profiles, "session_scope", session)

    with session() as db:
        for subject in ("alice", "bob"):
            db.add(User(external_id=subject, consent_flags={"health_data_processing": True, "personalization": True}))

    yield session
    engine.dispose()


def test_dispatch_async_cleans_up_orphaned_task_when_apply_async_fails():
    deleted_tasks = []

    fake_store = SimpleNamespace(
        create_task=lambda subject, **kw: "orphaned-task-123",
        load_history=lambda subject, conv_id, **kw: [],
        delete_task=lambda subject, task_id, **kw: deleted_tasks.append((subject, task_id)) or True,
    )

    class FailingLlmHandler:
        def apply_async(self, *args, **kwargs):
            raise TimeoutError("Celery broker connection timeout")

    service = ChatService(
        store=fake_store,
        llm_handler=FailingLlmHandler(),
    )

    with pytest.raises(QueueUnavailableError, match="hàng đợi"):
        asyncio.run(service.dispatch_async_chat("Xin chào", "alice"))

    # Verify orphaned task was cleaned up
    assert deleted_tasks == [("alice", "orphaned-task-123")]


def test_store_delete_task_removes_record_from_database(memory_db):
    task_id = store.create_task("alice")
    # Verify task exists
    store.require_task_owner("alice", task_id)

    # Bob cannot delete Alice's task
    assert store.delete_task("bob", task_id) is False
    store.require_task_owner("alice", task_id)

    # Alice deletes her task
    assert store.delete_task("alice", task_id) is True

    # Now task is gone
    with pytest.raises(profiles.PersonalizationNotFound):
        store.require_task_owner("alice", task_id)


def test_worker_idempotency_returns_cached_result_without_rerunning_chat(memory_db, monkeypatch):
    task_id = store.create_task("alice")
    call_counts = {"runs": 0}

    def fake_run_chat(question, user_id, conversation_id=None, bot_id=None, deadline_monotonic=None):
        call_counts["runs"] += 1
        return {"content": "Phản hồi đầu tiên", "status": "ok", "run_id": call_counts["runs"]}

    monkeypatch.setattr("memory.chat.run_chat", fake_run_chat)

    # First execution: LangGraph runs and stores result
    result1 = llm_handle_message(
        bot_id="health-inbody-agent",
        user_id="alice",
        question="Tư vấn dinh dưỡng",
        task_id=task_id,
    )

    assert result1["content"] == "Phản hồi đầu tiên"
    assert result1["run_id"] == 1
    assert call_counts["runs"] == 1

    # Verify task status is 'completed' in DB
    cached = store.get_task_if_completed("alice", task_id)
    assert cached is not None
    assert cached["content"] == "Phản hồi đầu tiên"

    # Second execution (simulating Celery at-least-once duplicate delivery)
    result2 = llm_handle_message(
        bot_id="health-inbody-agent",
        user_id="alice",
        question="Tư vấn dinh dưỡng",
        task_id=task_id,
    )

    # Must return cached result without calling run_chat again
    assert result2["content"] == "Phản hồi đầu tiên"
    assert result2["run_id"] == 1
    assert call_counts["runs"] == 1  # Crucial: run_chat was NOT executed again!


def test_worker_marks_task_failed_on_exception(memory_db, monkeypatch):
    task_id = store.create_task("alice")

    def failing_run_chat(*args, **kwargs):
        raise RuntimeError("LangGraph runtime execution failure")

    monkeypatch.setattr("memory.chat.run_chat", failing_run_chat)

    with pytest.raises(RuntimeError, match="LangGraph runtime execution failure"):
        llm_handle_message(
            bot_id="health-inbody-agent",
            user_id="alice",
            question="Lỗi hệ thống",
            task_id=task_id,
        )

    # Verify task status is 'failed' in DB
    with memory_db() as db:
        row = db.query(ChatTask).filter(ChatTask.id == store._uuid(task_id)).first()
        assert row is not None
        assert row.status == "failed"
        assert "LangGraph runtime execution failure" in (row.result_payload or "")

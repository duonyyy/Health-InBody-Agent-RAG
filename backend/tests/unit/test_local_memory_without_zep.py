"""Regression suite verifying complete Zep removal while preserving PostgreSQL local memory.

Covers:
- Clean app import and startup with zep_cloud explicitly blocked and no ZEP_* env vars.
- Zero outbound network / Zep calls across sync chat, async worker, facts, consent, and retention.
- Local conversations, ownership isolation, server-only history, facts propose/confirm/delete/expire.
- Local retention/purge Celery task without external maintenance.
- Legacy external_memory JSON flags in DB: no crash, no network call, no fake deletion timestamp,
  and does not block revoking local health_data_processing/personalization consents.
- Deprecated external routes return 404 without mutating local PostgreSQL memory.
- Urgent & tool-only fast paths and response cache isolation invariants preserved.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")

from agents import composer, graph
from core.response_cache import is_cacheable_public_rag_request
from jobs import tasks
from memory import chat, store
from memory.models import ChatTask, MemoryFact
from persistence import personalization_service as profiles
from persistence.database import Base
from persistence.models import ChatMessage, User

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture
def isolated_memory_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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
        db.add(
            User(
                external_id="alice",
                consent_flags={"health_data_processing": True, "personalization": True},
            )
        )
        db.add(
            User(
                external_id="bob",
                consent_flags={"health_data_processing": True, "personalization": True},
            )
        )
        # User with legacy external_memory JSON traces from before Zep removal.
        db.add(
            User(
                external_id="legacy-user",
                consent_flags={
                    "health_data_processing": True,
                    "personalization": True,
                    "external_memory": True,
                    "external_memory_sync_pending": True,
                    "external_memory_deletion_pending": True,
                    "external_memory_consented_at": "2026-09-29T00:00:00+00:00",
                    "external_memory_synced_at": "2026-09-30T00:00:00+00:00",
                },
            )
        )
    yield session
    engine.dispose()


@pytest.fixture
def block_outbound_network(monkeypatch):
    def _no_network(*args, **kwargs):
        raise AssertionError("Outbound network call is forbidden in local-memory tests")

    monkeypatch.setattr(socket, "create_connection", _no_network)


def test_app_imports_and_starts_without_zep_sdk_or_zep_env():
    """Run in a fresh subprocess with zep_cloud blocked in sys.meta_path and all ZEP_* stripped."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("ZEP_")}
    env.update(
        PYTHONPATH=str(BACKEND_SRC),
        DATABASE_URL="sqlite://",
        AUTH_MODE="development",
        BM25_AUTOLOAD="false",
        LLM_PROVIDER="none",
    )
    code = r"""
import importlib, sys

class BlockZep:
    def find_spec(self, fullname, path, target=None):
        if fullname == "zep_cloud" or fullname.startswith("zep_cloud.") or fullname in ("memory.zep_memory", "memory.sync"):
            raise ModuleNotFoundError(f"Blocked removed module: {fullname}")
        return None

sys.meta_path.insert(0, BlockZep())
api = importlib.import_module("api.app")
from agents import graph
from jobs import tasks
from memory import chat, store
from persistence import personalization_service

assert "zep_cloud" not in sys.modules
assert "memory.zep_memory" not in sys.modules
assert "memory.sync" not in sys.modules
assert api.app is not None
"""
    res = subprocess.run(
        [sys.executable, "-B", "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, f"Subprocess import failed:\n{res.stderr}"


def test_local_facts_lifecycle_confirm_delete_expire_and_owner_isolation(
    isolated_memory_db, block_outbound_network, monkeypatch
):
    from api.app import app

    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("BM25_AUTOLOAD", "false")
    client = TestClient(app)
    alice_h = {"X-Dev-User-Id": "alice"}
    bob_h = {"X-Dev-User-Id": "bob"}

    # 1. Create conversation & record user turn.
    conv_resp = client.post("/me/conversations", headers=alice_h)
    assert conv_resp.status_code == 201
    cid = conv_resp.json()["conversation_id"]
    turn = store.record_turn("alice", cid, "Tôi thích tập bơi và ăn chay.", "Đã ghi nhận.")

    # 2. Propose fact grounded in user's own message.
    prop_resp = client.post(
        "/me/memory/facts",
        headers=alice_h,
        json={
            "message_id": turn["user_message_id"],
            "kind": "dietary_preference",
            "text": "ăn chay",
        },
    )
    assert prop_resp.status_code == 201
    fact_id = prop_resp.json()["id"]
    assert prop_resp.json()["status"] == "pending"

    # Pending fact is NOT in confirmed context yet.
    ctx_pending = profiles.build_confirmed_personalization_context("alice")
    assert ctx_pending["confirmed_memory"] == []
    assert "external_memory_consent" not in ctx_pending

    # Bob cannot confirm or delete Alice's fact or read Alice's conversation.
    assert client.post(f"/me/memory/facts/{fact_id}/confirm", headers=bob_h).status_code == 404
    assert client.delete(f"/me/memory/facts/{fact_id}", headers=bob_h).status_code == 404
    assert client.get(f"/me/conversations/{cid}", headers=bob_h).status_code == 404
    assert client.delete(f"/me/conversations/{cid}", headers=bob_h).status_code == 404

    # 3. Confirm fact -> enters confirmed context and memory recall fast-path!
    conf_resp = client.post(f"/me/memory/facts/{fact_id}/confirm", headers=alice_h)
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "confirmed"

    list_resp = client.get("/me/memory/facts", headers=alice_h)
    assert list_resp.status_code == 200
    assert list(list_resp.json().keys()) == ["items"]
    assert len(list_resp.json()["items"]) == 1

    ctx_confirmed = profiles.build_confirmed_personalization_context("alice")
    assert [f["text"] for f in ctx_confirmed["confirmed_memory"]] == ["ăn chay"]

    recalled = graph.multi_agent_handle(
        "Bạn nhớ gì về tôi?",
        user_id="alice",
        user_profile=ctx_confirmed,
    )
    assert recalled["fast_path"] == "personal_memory"
    assert "ăn chay" in recalled["content"]

    # 4. Delete fact -> immediately absent from context.
    assert client.delete(f"/me/memory/facts/{fact_id}", headers=alice_h).status_code == 204
    assert profiles.build_confirmed_personalization_context("alice")["confirmed_memory"] == []

    # 5. Expired fact is never recalled and is purged by local Celery task purge_memory.
    prop2 = store.propose_fact("alice", turn["user_message_id"], "exercise_preference", "Tôi thích tập bơi")
    store.confirm_fact("alice", prop2["id"])
    with isolated_memory_db() as db:
        db.query(MemoryFact).filter_by(id=uuid.UUID(prop2["id"])).update(
            {MemoryFact.expires_at: store.now() - timedelta(seconds=5)}
        )
    assert profiles.build_confirmed_personalization_context("alice")["confirmed_memory"] == []

    purge_fn = getattr(tasks.purge_memory, "run", tasks.purge_memory)
    purge_result = purge_fn()
    assert purge_result["facts_removed"] == 1
    assert "external_operations_completed" not in purge_result
    assert "external_operations_pending" not in purge_result


def test_legacy_external_memory_flags_do_not_crash_call_network_or_block_local_consent_revoke(
    isolated_memory_db, block_outbound_network, monkeypatch
):
    from api.app import app

    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("BM25_AUTOLOAD", "false")
    client = TestClient(app)
    headers = {"X-Dev-User-Id": "legacy-user"}

    # 1. Profile read does not expose removed external_memory flags as active consent.
    prof = client.get("/me/profile", headers=headers)
    assert prof.status_code == 200
    assert prof.json()["consent_flags"] == {
        "health_data_processing": True,
        "personalization": True,
    }

    # 2. Local memory & chat work normally for user with legacy flags, with zero network calls.
    cid = store.open_conversation("legacy-user")["conversation_id"]
    turn = store.record_turn("legacy-user", cid, "Tôi ăn chay.", "Đã hiểu.")
    fact = store.propose_fact("legacy-user", turn["user_message_id"], "dietary_preference", "Tôi ăn chay")
    store.confirm_fact("legacy-user", fact["id"])
    assert store.confirmed_facts("legacy-user")[0]["text"] == "Tôi ăn chay"

    # 3. Revoking local health_data_processing & personalization consents MUST SUCCEED
    #    (no longer blocked by legacy external_memory=True!), AND must preserve legacy
    #    audit keys without fabricating external_memory_deleted_at.
    revoke = client.patch(
        "/me/profile",
        headers=headers,
        json={"consent_flags": {"health_data_processing": False, "personalization": False}},
    )
    assert revoke.status_code == 200
    assert revoke.json()["consent_flags"] == {
        "health_data_processing": False,
        "personalization": False,
    }

    # Verify legacy DB row kept untouched metadata & did not forge deletion proof.
    with isolated_memory_db() as db:
        stored_flags = db.query(User).filter_by(external_id="legacy-user").one().consent_flags
        assert stored_flags["health_data_processing"] is False
        assert stored_flags["personalization"] is False
        assert stored_flags["external_memory_deletion_pending"] is True
        assert stored_flags["external_memory_synced_at"] == "2026-09-30T00:00:00+00:00"
        assert "external_memory_deleted_at" not in stored_flags
        assert profiles.legacy_external_memory_status(stored_flags) == "unverified_external_state"
        assert profiles.legacy_external_memory_status({"health_data_processing": True}) == "none"

    # After local consent revocation, local memory reads are blocked with 409.
    assert client.get("/me/memory/facts", headers=headers).status_code == 409
    assert profiles.safe_build_confirmed_context("legacy-user")["reason"] == "consent_required"


def test_removed_external_routes_return_404_and_preserve_local_memory(
    isolated_memory_db, block_outbound_network, monkeypatch
):
    from api.app import app

    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("BM25_AUTOLOAD", "false")
    client = TestClient(app)
    headers = {"X-Dev-User-Id": "alice"}

    cid = store.open_conversation("alice")["conversation_id"]
    turn = store.record_turn("alice", cid, "Tôi ăn chay.", "Đã hiểu.")
    fact = store.propose_fact("alice", turn["user_message_id"], "dietary_preference", "Tôi ăn chay")
    store.confirm_fact("alice", fact["id"])

    # Calling removed external routes MUST return 404 and MUST NOT delete local PostgreSQL facts/conversations!
    assert client.put(
        "/me/memory-consent",
        headers=headers,
        json={"acknowledged_external_processing": True},
    ).status_code == 404
    assert client.post("/me/memory/sync", headers=headers).status_code == 404
    assert client.delete("/me/memory", headers=headers).status_code == 404

    # Local PostgreSQL data remains intact.
    assert len(store.confirmed_facts("alice")) == 1
    assert len(store.load_history("alice", cid)) == 2


def test_urgent_tool_only_and_cache_isolation_without_zep(block_outbound_network, monkeypatch):
    # Urgent bypasses DB, history, LLM, retrieval.
    def forbidden(*args, **kwargs):
        raise AssertionError("Urgent must bypass storage/LLM/retrieval")

    monkeypatch.setattr(profiles, "safe_build_confirmed_context", forbidden)
    monkeypatch.setattr(store, "load_history", forbidden)
    monkeypatch.setattr(store, "record_turn", forbidden)
    monkeypatch.setattr(graph, "openai_chat_complete", forbidden)
    monkeypatch.setattr(graph, "hybrid_search", forbidden)

    urgent = chat.run_chat("Tôi đau ngực và khó thở.", "alice", "fake-session")
    assert urgent["fast_path"] == "urgent_safety"
    assert urgent["memory_status"] == "skipped_urgent"

    bmi = graph.multi_agent_handle("Tôi nặng 72kg, cao 170cm. BMI?", user_id="alice")
    assert bmi["fast_path"] == "inbody_tools"

    # Response cache refuses personalized requests (confirmed local facts / user_id).
    assert not is_cacheable_public_rag_request(
        question="BMI là gì?",
        selected_agents=[graph.RAG_AGENT],
        rag_agent=graph.RAG_AGENT,
        safety_result={"risk_level": "low"},
        user_id=None,
        history=[],
        personalization_context={
            "available": True,
            "confirmed_memory": [{"text": "Tôi thích câu trả lời ngắn gọn."}],
        },
        user_profile={},
        tool_results=[],
        errors=[],
    )
    assert not is_cacheable_public_rag_request(
        question="BMI là gì?",
        selected_agents=[graph.RAG_AGENT],
        rag_agent=graph.RAG_AGENT,
        safety_result={"risk_level": "low"},
        user_id="alice",
        history=[],
        personalization_context={},
        user_profile={},
        tool_results=[],
        errors=[],
    )


def test_sync_and_async_chat_use_local_postgres_history_with_zero_zep(
    isolated_memory_db, block_outbound_network, monkeypatch
):
    from api.app import app

    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("BM25_AUTOLOAD", "false")
    seen_kwargs = []

    def fake_handle(question, **kwargs):
        seen_kwargs.append(kwargs)
        return {
            "content": "Đã ghi nhận câu hỏi của bạn.",
            "status": "ok",
            "errors": [],
            "safety_result": {"risk_level": "low"},
        }

    monkeypatch.setattr(chat, "multi_agent_handle", fake_handle)
    client = TestClient(app)
    headers = {"X-Dev-User-Id": "alice"}

    # Sync /chat/complete
    r1 = client.post(
        "/chat/complete",
        headers=headers,
        json={"user_message": "Tôi ăn chay.", "sync_request": True},
    )
    assert r1.status_code == 200
    cid = r1.json()["response"]["conversation_id"]
    assert "use_zep_memory" not in seen_kwargs[-1]

    # Sync /agent/answer reusing same conversation_id gets server history
    r2 = client.post(
        "/agent/answer",
        headers=headers,
        json={"question": "Nhắc lại giúp tôi.", "conversation_id": cid},
    )
    assert r2.status_code == 200
    assert seen_kwargs[-1]["history"][0]["content"] == "Tôi ăn chay."
    assert "use_zep_memory" not in seen_kwargs[-1]

    # Async worker llm_handle_message uses same local PostgreSQL history & zero Zep
    task_id = store.create_task("alice")
    worker_fn = getattr(tasks.llm_handle_message, "run", tasks.llm_handle_message)
    worker_res = worker_fn("health-inbody-agent", "alice", "Tiếp tục nhé.", cid, task_id)
    assert worker_res["conversation_id"] == cid
    assert len(seen_kwargs[-1]["history"]) >= 2
    assert "use_zep_memory" not in seen_kwargs[-1]
    assert "zep_cloud" not in sys.modules


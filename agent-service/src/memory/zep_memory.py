"""Zep Cloud mirror/ranking adapter for explicitly confirmed preferences.

PostgreSQL owns the canonical facts. This mirror is separate from the
shared medical RAG corpus. No Zep payload is an instruction or clinical proof.
"""

import hashlib
import hmac
import json
import os
import re
from functools import lru_cache
from typing import Any

from harness.guards import has_untrusted_instruction


def _secret() -> bytes:
    value = os.getenv("ZEP_ID_SECRET", "")
    if len(value) < 32:
        raise ValueError("ZEP_ID_SECRET must contain at least 32 characters")
    return value.encode("utf-8")


def available() -> bool:
    return (os.getenv("ZEP_MEMORY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
            and bool(os.getenv("ZEP_API_KEY")) and len(os.getenv("ZEP_ID_SECRET", "")) >= 32)


def timeout_seconds() -> float:
    return min(5.0, max(0.5, float(os.getenv("ZEP_HTTP_TIMEOUT_SECONDS", "2"))))


def _request_options() -> dict:
    return {"max_retries": 0}


def user_id_for(subject: str) -> str:
    if not subject:
        raise ValueError("Authenticated subject is required")
    digest = hmac.new(_secret(), f"user:{subject}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"health-{digest}"


def thread_id_for(subject: str, conversation_id: str = "main") -> str:
    if not conversation_id or len(conversation_id) > 100:
        raise ValueError("Invalid conversation identifier")
    digest = hmac.new(_secret(), f"thread:{subject}:{conversation_id}".encode("utf-8"),
                      hashlib.sha256).hexdigest()
    return f"thread-{digest}"


@lru_cache(maxsize=1)
def _sdk_client(api_key: str, timeout: float):
    from zep_cloud import Zep
    return Zep(api_key=api_key, timeout=timeout)


def _client():
    key = os.getenv("ZEP_API_KEY")
    if not key:
        raise RuntimeError("Zep API key is not configured")
    return _sdk_client(key, timeout_seconds())


def _message(**kwargs):
    from zep_cloud import Message
    return Message(**kwargs)


def _status_code(exc: Exception) -> Any:
    return getattr(exc, "status_code", None) or getattr(exc, "status", None)


def _ensure_exists(get, create, identifier: dict, create_args: dict) -> None:
    try:
        get(**identifier, request_options=_request_options())
        return
    except Exception as exc:
        if _status_code(exc) != 404:
            raise
    try:
        create(**create_args, request_options=_request_options())
    except Exception as exc:
        # Another request may create it between GET and POST.
        if _status_code(exc) != 409:
            raise


def recall(subject: str, query: str, *, consent: bool, facts: list[dict]) -> str:
    """Search only this user's graph; never promote results to trusted policy."""
    if not consent or not available() or not subject or not query.strip():
        return ""
    try:
        results = _client().graph.search(
            user_id=user_id_for(subject), query=query.strip()[:400], scope="episodes", limit=3,
            request_options=_request_options(),
        )
    except Exception as exc:
        if _status_code(exc) == 404:
            return ""
        raise
    canonical = {item["id"]: item for item in facts if item.get("status") == "confirmed"}
    snippets, seen = [], set()
    for episode in getattr(results, "episodes", None) or []:
        content = str(getattr(episode, "content", "") or "").strip()
        if not content or has_untrusted_instruction(content):
            continue
        # Provider output may rank facts, but only current PostgreSQL content is admitted.
        for fact_id in re.findall(r'"fact_id"\s*:\s*"([a-f0-9-]{36})"', content):
            fact = canonical.get(fact_id)
            if fact and fact_id not in seen:
                snippets.append(f"- Người dùng đã xác nhận: {fact['text']}")
                seen.add(fact_id)
    return "\n".join(snippets)[:1000]


def remember_confirmed(subject: str, facts: list[dict], *, consent: bool) -> bool:
    """Mirror explicitly confirmed facts; never accept a raw chat transcript."""
    if not consent or not available() or not subject or not facts:
        return False
    if len(facts) > 20 or any(item.get("status") != "confirmed" or not item.get("confirmed_at")
                             or has_untrusted_instruction(item["text"]) for item in facts):
        raise ValueError("Only bounded confirmed facts may be exported")
    client = _client()
    zep_user = user_id_for(subject)
    zep_thread = thread_id_for(subject, "confirmed-facts-v1")
    _ensure_exists(client.user.get, client.user.add,
                   {"user_id": zep_user}, {"user_id": zep_user})
    _ensure_exists(client.thread.get, client.thread.create,
                   {"thread_id": zep_thread, "limit": 1},
                   {"thread_id": zep_thread, "user_id": zep_user})
    client.thread.add_messages(
        thread_id=zep_thread,
        messages=[_message(role="user", content=json.dumps({
            "schema": "health.confirmed-memory.v1", "fact_id": fact["id"], "text": fact["text"],
            "confirmed_at": fact["confirmed_at"], "expires_at": fact["expires_at"],
        }, ensure_ascii=False)) for fact in facts],
        request_options=_request_options(),
    )
    return True


def forget(subject: str) -> None:
    """Delete this user's Zep graph and threads; caller handles other stores."""
    try:
        _client().user.delete(user_id=user_id_for(subject), request_options=_request_options())
    except Exception as exc:
        if _status_code(exc) != 404:
            raise

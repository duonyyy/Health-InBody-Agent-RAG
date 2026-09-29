"""Real SDK serialization with HTTP MockTransport; never contacts Zep Cloud."""
import json
import httpx
import pytest

zep_cloud = pytest.importorskip("zep_cloud")
from memory import zep_memory


def test_real_sdk_confirmed_only_roundtrip(monkeypatch):
    monkeypatch.setenv("ZEP_MEMORY_ENABLED", "true")
    monkeypatch.setenv("ZEP_API_KEY", "synthetic-test-not-a-secret")
    monkeypatch.setenv("ZEP_ID_SECRET", "synthetic-test-id-key-at-least-32-characters")
    fact = {"id": "b53b0a93-6df9-4299-979a-ad351dc64584", "status": "confirmed",
            "text": "Tôi thích câu trả lời ngắn gọn.", "confirmed_at": "2026-09-29T00:00:00Z",
            "expires_at": "2027-03-28T00:00:00Z"}
    calls, exported = [], []

    def respond(request):
        payload = json.loads(request.content) if request.content else {}
        calls.append((request.method, str(request.url), payload))
        if request.method == "GET":
            return httpx.Response(404, json={"message": "not found"})
        if payload.get("scope") == "episodes":
            return httpx.Response(200, json={"episodes": [{"uuid": "episode-test",
                "created_at": fact["confirmed_at"], "content": exported[0]}]})
        if "messages" in payload:
            exported.extend(item["content"] for item in payload["messages"])
        return httpx.Response(200, json={"user_id": payload.get("user_id", "test"),
                                        "thread_id": payload.get("thread_id", "test"), "message": "success"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = zep_cloud.Zep(api_key="synthetic-test-not-a-secret", httpx_client=http, timeout=2)
        monkeypatch.setattr(zep_memory, "_client", lambda: client)
        assert zep_memory.remember_confirmed("synthetic-alice", [fact], consent=True)
        assert json.loads(exported[0])["fact_id"] == fact["id"]
        assert fact["text"] in zep_memory.recall("synthetic-alice", "response_preference", consent=True, facts=[fact])
        zep_memory.forget("synthetic-alice")
    assert "synthetic-alice" not in str(calls)
    assert sum(method == "DELETE" for method, _, _ in calls) == 1
    assert len(exported) == 1


def test_real_sdk_transient_error_is_not_retried(monkeypatch):
    monkeypatch.setenv("ZEP_ID_SECRET", "synthetic-test-id-key-at-least-32-characters")
    attempts = []

    def fail(request):
        attempts.append(request.method)
        return httpx.Response(503, json={"message": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(fail)) as http:
        client = zep_cloud.Zep(api_key="synthetic-test-not-a-secret", httpx_client=http, timeout=2)
        monkeypatch.setattr(zep_memory, "_client", lambda: client)
        with pytest.raises(Exception) as error:
            zep_memory.forget("synthetic-alice")
        assert getattr(error.value, "status_code", None) == 503
    assert attempts == ["DELETE"]

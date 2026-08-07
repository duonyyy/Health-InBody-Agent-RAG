from llm import client as brain
import pytest


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": "general_chat"}}


class _ThinkingOnlyResponse(_FakeResponse):
    def json(self):
        return {
            "message": {
                "content": "",
                "thinking": "Reasoning used the available output budget.",
            }
        }


def test_ollama_payload_disables_thinking_and_uses_task_timeout(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(brain.requests, "post", fake_post)

    result = brain._chat_with_ollama(
        [{"role": "user", "content": "Xin chào"}],
        model="test-model",
        max_tokens=16,
        think=False,
        timeout=8,
    )

    assert result == "general_chat"
    assert captured["json"]["think"] is False
    assert captured["json"]["options"]["num_predict"] == 16
    assert captured["timeout"] == 8


def test_ollama_auto_mode_omits_model_specific_think_field(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update({"json": json, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(brain.requests, "post", fake_post)

    brain._chat_with_ollama(
        [{"role": "user", "content": "Hello"}],
        model="replaceable-model",
        think=None,
        timeout=9,
    )

    assert captured["json"]["model"] == "replaceable-model"
    assert "think" not in captured["json"]
    assert captured["timeout"] == 9


def test_thinking_only_response_fails_explicitly(monkeypatch):
    monkeypatch.setattr(
        brain.requests,
        "post",
        lambda *args, **kwargs: _ThinkingOnlyResponse(),
    )

    with pytest.raises(RuntimeError, match="OLLAMA_THINK"):
        brain._chat_with_ollama(
            [{"role": "user", "content": "Route this"}],
            model="thinking-model",
            think=None,
            max_tokens=8,
        )


def test_route_fallback_handles_vietnamese_without_accents(monkeypatch):
    monkeypatch.setattr(brain, "openai_chat_complete", lambda *args, **kwargs: "")

    route = brain.detect_route([], "Goi y lich tap 3 buoi/tuan")

    assert route == brain.AGENT_TOOLS_ROUTE


def test_router_uses_small_non_thinking_budget(monkeypatch):
    captured = {}

    def fake_complete(*args, **kwargs):
        captured.update(kwargs)
        return "general_chat"

    monkeypatch.setattr(brain, "openai_chat_complete", fake_complete)

    assert brain.detect_route([], "Xin chào") == brain.GENERAL_CHAT_ROUTE
    assert "think" not in captured
    assert captured["max_tokens"] == brain.LLM_ROUTER_MAX_TOKENS
    assert captured["timeout"] == brain.LLM_ROUTER_TIMEOUT

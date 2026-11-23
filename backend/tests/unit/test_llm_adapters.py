"""Unit tests for LLM Provider Strategy / Adapter Pattern.

Validates (references/factory-strategy-adapter.md & AGENTS.md 4.1):
- LLMAdapter protocol conformance across all provider strategies.
- Provider factory dispatch (get_llm_adapter, ADAPTERS).
- Extensibility via register_llm_adapter without modifying core routers or agent graphs.
- Behavior parity and error handling across OllamaAdapter, OpenAIAdapter, CustomApiAdapter, DisabledAdapter.
"""

import pytest

from llm import client as llm_client
from llm.client import (
    ADAPTERS,
    CustomApiAdapter,
    DisabledAdapter,
    LLMAdapter,
    OllamaAdapter,
    OpenAIAdapter,
    get_llm_adapter,
    openai_chat_complete,
    register_llm_adapter,
)


def test_adapters_conform_to_llm_adapter_protocol():
    assert isinstance(OllamaAdapter(), LLMAdapter)
    assert isinstance(OpenAIAdapter(), LLMAdapter)
    assert isinstance(CustomApiAdapter(), LLMAdapter)
    assert isinstance(DisabledAdapter(), LLMAdapter)


def test_get_llm_adapter_factory():
    assert isinstance(get_llm_adapter("ollama"), OllamaAdapter)
    assert isinstance(get_llm_adapter("openai"), OpenAIAdapter)
    assert isinstance(get_llm_adapter("custom"), CustomApiAdapter)
    assert isinstance(get_llm_adapter("vietnamese_llm"), CustomApiAdapter)
    assert isinstance(get_llm_adapter("none"), DisabledAdapter)
    assert isinstance(get_llm_adapter("disabled"), DisabledAdapter)
    assert isinstance(get_llm_adapter("offline"), DisabledAdapter)
    # Unknown provider defaults to Ollama
    assert isinstance(get_llm_adapter("unknown_provider"), OllamaAdapter)


def test_disabled_adapter_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "disabled")
    with pytest.raises(RuntimeError, match="LLM provider is disabled"):
        openai_chat_complete([{"role": "user", "content": "hi"}])


def test_ollama_and_custom_adapters_reject_raw_flag():
    with pytest.raises(ValueError, match="raw=True is only supported for OpenAI provider"):
        OllamaAdapter().chat([{"role": "user", "content": "hi"}], raw=True)

    with pytest.raises(ValueError, match="raw=True is not supported for custom API provider"):
        CustomApiAdapter().chat([{"role": "user", "content": "hi"}], raw=True)


def test_custom_adapter_registration_and_dispatch(monkeypatch):
    calls = []

    class MockCloudLLMAdapter:
        def chat(self, messages=(), **kwargs):
            calls.append((messages, kwargs))
            return "Response from Mock Cloud LLM"

    mock_adapter = MockCloudLLMAdapter()
    register_llm_adapter("mock_cloud", mock_adapter)

    try:
        assert get_llm_adapter("mock_cloud") is mock_adapter

        monkeypatch.setattr(llm_client, "LLM_PROVIDER", "mock_cloud")
        response = openai_chat_complete(
            [{"role": "user", "content": "Kiểm tra huyết áp"}],
            model="cloud-model-v1",
            temperature=0.3,
            max_tokens=100,
        )

        assert response == "Response from Mock Cloud LLM"
        assert len(calls) == 1
        assert calls[0][0][0]["content"] == "Kiểm tra huyết áp"
        assert calls[0][1]["model"] == "cloud-model-v1"
        assert calls[0][1]["temperature"] == 0.3
        assert calls[0][1]["max_tokens"] == 100
    finally:
        # Clean up registry
        ADAPTERS.pop("mock_cloud", None)

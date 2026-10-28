"""Regression coverage for safe, exact-match RAG response caching."""

import time

from agents import composer, graph
from core import cache as cache_module
from core.response_cache import (
    build_llm_response_cache_key,
    is_cacheable_public_rag_request,
)


def _cacheable_state(**updates):
    state = {
        "question": "PBF có nghĩa là gì?",
        "selected_agents": [graph.RAG_AGENT],
        "deadline_monotonic": time.monotonic() + 30,
        "retrieved_docs": [
            {
                "document_id": "doc-pbf",
                "chunk_id": "chunk-pbf-1",
                "content": "PBF là tỷ lệ phần trăm mỡ trong cơ thể.",
                "source": "InBody guide",
            }
        ],
        "tool_results": [],
        "safety_result": {"risk_level": "low"},
        "personalization_context": {},
        "user_profile": {},
        "history": [],
        "memory_context": "",
        "errors": [],
        "agent_trace": [],
        "limitations": [],
    }
    state.update(updates)
    return state


def test_response_cache_key_is_hashed_and_versioned():
    messages = [{"role": "user", "content": "private-looking input"}]
    common = {
        "messages": messages,
        "model_config": {"provider": "ollama", "model": "model-a"},
        "corpus_fingerprint": {"corpus_version": "corpus-v1", "collection_name": "active"},
    }

    key = build_llm_response_cache_key(**common)

    assert "private-looking input" not in key
    assert key == build_llm_response_cache_key(**common)
    assert key != build_llm_response_cache_key(
        **{**common, "model_config": {"provider": "ollama", "model": "model-b"}}
    )
    assert key != build_llm_response_cache_key(
        **{
            **common,
            "corpus_fingerprint": {
                "corpus_version": "corpus-v2",
                "collection_name": "active",
            },
        }
    )

    try:
        build_llm_response_cache_key(
            messages=messages,
            model_config={"provider": "ollama", "model": "model-a"},
            corpus_fingerprint={"corpus_version": "unknown"},
        )
    except ValueError as exc:
        assert "verified corpus_version" in str(exc)
    else:
        raise AssertionError("Unknown corpus versions must not produce reusable cache keys")


def test_public_rag_cache_policy_rejects_personal_or_unsafe_context():
    base = {
        "question": "PBF có nghĩa là gì?",
        "selected_agents": [graph.RAG_AGENT],
        "rag_agent": graph.RAG_AGENT,
        "safety_result": {"risk_level": "low"},
        "user_id": None,
        "history": [],
        "personalization_context": {},
        "user_profile": {},
        "memory_context": "",
        "tool_results": [],
        "errors": [],
    }
    assert is_cacheable_public_rag_request(**base)

    assert not is_cacheable_public_rag_request(
        **{**base, "question": "PBF của Anna có nghĩa là gì?"}
    )
    assert not is_cacheable_public_rag_request(
        **{**base, "question": "Làm sao giảm mỡ nội tạng?"}
    )
    assert not is_cacheable_public_rag_request(
        **{**base, "question": "Tôi có PBF 28%, chỉ số này nghĩa là gì?"}
    )
    assert not is_cacheable_public_rag_request(
        **{**base, "question": "Mình bị đau vai, nên tập thế nào?"}
    )
    assert not is_cacheable_public_rag_request(
        **{
            **base,
            "personalization_context": {"available": True, "profile": {"age": 35}},
        }
    )
    assert not is_cacheable_public_rag_request(
        **{**base, "safety_result": {"risk_level": "medical_caution"}}
    )
    assert not is_cacheable_public_rag_request(
        **{**base, "selected_agents": [graph.RAG_AGENT, graph.WEB_SEARCH_AGENT]}
    )


def test_memory_cache_fallback_has_a_hard_entry_limit(monkeypatch):
    original_cache = cache_module._memory_cache.copy()
    cache_module._memory_cache.clear()
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: None)
    monkeypatch.setattr(cache_module, "CACHE_MEMORY_MAX_ENTRIES", 2)

    try:
        cache_module.cache_set("cache-test-one", "one", ttl_seconds=60)
        cache_module.cache_set("cache-test-two", "two", ttl_seconds=60)
        cache_module.cache_set("cache-test-three", "three", ttl_seconds=60)

        assert len(cache_module._memory_cache) == 2
        assert cache_module.cache_get("cache-test-one") is None
        assert cache_module.cache_get("cache-test-three") == "three"
    finally:
        cache_module._memory_cache.clear()
        cache_module._memory_cache.update(original_cache)


def test_composer_reuses_only_exact_supported_public_rag_answer(monkeypatch):
    stored = {}
    llm_calls = []

    monkeypatch.setattr(composer, "llm_response_cache_enabled", lambda: True)
    monkeypatch.setattr(composer, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(composer, "get_search_stats", lambda: {
        "corpus_version": "corpus-v1",
        "collection_name": "active",
        "snapshot_point_count": 1,
    })
    monkeypatch.setattr(composer, "llm_response_cache_get", lambda key: stored.get(key))
    monkeypatch.setattr(
        composer,
        "llm_response_cache_set",
        lambda key, value, ttl_seconds: stored.__setitem__(key, value),
    )
    monkeypatch.setattr(composer, "llm_response_cache_delete", lambda key: stored.pop(key, None))

    def fake_llm(messages, **kwargs):
        llm_calls.append(messages)
        return "PBF là tỷ lệ phần trăm mỡ trong cơ thể [1]."

    monkeypatch.setattr(graph, "openai_chat_complete", fake_llm)
    first = graph.response_composer_agent(_cacheable_state())
    second = graph.response_composer_agent(_cacheable_state())

    assert len(llm_calls) == 1
    assert first["final_answer"] == second["final_answer"]
    assert second["claim_evidence_links"][0]["document_id"] == "doc-pbf"
    assert any(item["action"] == "llm_response_cache_hit" for item in second["agent_trace"])


def test_composer_bypasses_cache_for_personalized_request(monkeypatch):
    cache_reads = []
    cache_writes = []
    llm_calls = []

    monkeypatch.setattr(composer, "llm_response_cache_enabled", lambda: True)
    monkeypatch.setattr(composer, "get_search_stats", lambda: {
        "corpus_version": "corpus-v1",
        "collection_name": "active",
        "snapshot_point_count": 1,
    })
    monkeypatch.setattr(composer, "llm_response_cache_get", lambda key: cache_reads.append(key))
    monkeypatch.setattr(
        composer,
        "llm_response_cache_set",
        lambda *args, **kwargs: cache_writes.append(args),
    )
    monkeypatch.setattr(composer, "llm_response_cache_delete", lambda key: None)
    monkeypatch.setattr(
        graph,
        "openai_chat_complete",
        lambda messages, **kwargs: llm_calls.append(messages)
        or "PBF là tỷ lệ phần trăm mỡ trong cơ thể [1].",
    )

    result = graph.response_composer_agent(
        _cacheable_state(
            user_id="authenticated-user",
            personalization_context={"available": True, "profile": {"age": 35}},
        )
    )

    assert len(llm_calls) == 1
    assert cache_reads == []
    assert cache_writes == []
    assert result["evidence_status"] == "supported"


def test_composer_disables_cache_when_provider_identity_is_ambiguous(monkeypatch):
    monkeypatch.setattr(composer, "llm_response_cache_enabled", lambda: True)
    monkeypatch.setattr(composer, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(composer, "OPENAI_API_KEY", "configured-fallback")

    key = composer._public_rag_response_cache_key(
        _cacheable_state(),
        [{"role": "user", "content": "generic prompt"}],
        "PBF có nghĩa là gì?",
        [graph.RAG_AGENT],
    )

    assert key == ""


def test_invalid_cached_answer_is_rejected_and_evicted(monkeypatch):
    deleted = []

    monkeypatch.setattr(composer, "llm_response_cache_enabled", lambda: True)
    monkeypatch.setattr(composer, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(composer, "get_search_stats", lambda: {
        "corpus_version": "corpus-v1",
        "collection_name": "active",
        "snapshot_point_count": 1,
    })
    monkeypatch.setattr(
        composer,
        "llm_response_cache_get",
        lambda key: "PBF chắc chắn chẩn đoán bệnh tim [99].",
    )
    monkeypatch.setattr(composer, "llm_response_cache_set", lambda *args, **kwargs: None)
    monkeypatch.setattr(composer, "llm_response_cache_delete", lambda key: deleted.append(key))
    monkeypatch.setattr(
        graph,
        "openai_chat_complete",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit should bypass LLM")
        ),
    )

    result = graph.response_composer_agent(_cacheable_state())

    assert result["evidence_status"] == "insufficient"
    assert "Không đủ bằng chứng" in result["final_answer"]
    assert deleted

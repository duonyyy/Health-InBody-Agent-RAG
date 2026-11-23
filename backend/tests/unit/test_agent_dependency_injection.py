"""Unit tests for Agent Dependency Injection (agents.dependencies).

Validates:
- Testing LangGraph nodes and multi_agent_handle WITHOUT monkey-patching.
- Explicit dependency injection via AgentDependencies container and AgentState['dependencies'].
- Strict isolation of external LLM and retrieval calls.
"""
from typing import Any, Dict, List, Optional
import pytest

from agents.dependencies import (
    AgentDependencies,
    resolve_agent_dependencies,
)
from agents.graph import multi_agent_handle
from agents.nodes.rag import rag_agent
from agents.nodes.web_search import web_search_agent
from agents.composer import response_composer_agent
from agents.state import AgentState


def test_resolve_agent_dependencies_prioritizes_injected():
    custom_search = lambda query, **kw: [{"title": "custom"}]
    custom_chat = lambda msgs, **kw: "custom answer"

    deps = AgentDependencies(
        search_fn=custom_search,
        openai_chat_fn=custom_chat,
    )
    state: AgentState = {"dependencies": deps}

    resolved = resolve_agent_dependencies(state)
    assert resolved.search_fn == custom_search
    assert resolved.openai_chat_fn == custom_chat
    # Unspecified dependencies fall back to non-None callables
    assert callable(resolved.medical_safety_fn)
    assert callable(resolved.answer_memory_fn)


def test_agent_dependencies_clone_with():
    base = AgentDependencies(
        openai_chat_fn=lambda msgs, **kw: "base",
    )
    overridden = base.clone_with(
        openai_chat_fn=lambda msgs, **kw: "new",
        search_fn=lambda q, **kw: [],
    )
    assert overridden.openai_chat_fn(None) == "new"
    assert overridden.search_fn("test") == []


def test_multi_agent_handle_with_injected_urgent_safety_without_monkeypatch():
    """Verify that multi_agent_handle uses injected medical_safety_fn without monkeypatching."""
    calls = []

    def mock_safety(question: str, medical_conditions=None, **kw):
        calls.append(question)
        return {
            "risk_level": "urgent",
            "disclaimer": "Cần cấp cứu",
            "recommended_action": "Đi bệnh viện",
        }

    deps = AgentDependencies(medical_safety_fn=mock_safety)

    result = multi_agent_handle(
        "Tôi bị đau đầu nhẹ",
        dependencies=deps,
    )

    assert len(calls) == 1
    assert calls[0] == "Tôi bị đau đầu nhẹ"
    assert result["fast_path"] == "urgent_safety"
    assert result["safety_result"]["risk_level"] == "urgent"
    assert "dừng tập ngay" in result["content"].lower()


def test_rag_agent_isolated_execution_with_injected_dependencies():
    """Verify rag_agent executes with pure injected search_fn and rewrite_fn without monkeypatch."""
    captured_queries = []

    def mock_rewrite(query: str, **kw):
        return [query, f"{query} mở rộng"]

    def mock_search(query: str, **kw):
        captured_queries.append(query)
        return [
            {
                "doc_id": f"doc-{len(captured_queries)}",
                "title": f"Doc for {query}",
                "content": "Nội dung bài tập",
                "content_type": "exercise",
            }
        ]

    deps = AgentDependencies(
        rewrite_fn=mock_rewrite,
        search_fn=mock_search,
    )

    state: AgentState = {
        "question": "Cách tập hít đất",
        "selected_agents": ["RAGAgent"],
        "agent_trace": [],
        "errors": [],
        "call_counts": {},
        "dependencies": deps,
    }

    next_state = rag_agent(state)

    assert len(captured_queries) >= 1
    assert "retrieved_docs" in next_state
    assert len(next_state["retrieved_docs"]) > 0


def test_response_composer_isolated_execution_with_injected_chat_fn():
    """Verify response_composer_agent uses injected LLM callable without monkeypatch."""
    llm_prompts = []

    def mock_openai(messages: List[Dict[str, str]], **kw) -> Optional[str]:
        llm_prompts.append(messages)
        return "Câu trả lời tổng hợp từ mock LLM."

    deps = AgentDependencies(
        openai_chat_fn=mock_openai,
        vietnamese_llm_fn=mock_openai,
    )

    state: AgentState = {
        "question": "Cho tôi lời khuyên về dinh dưỡng",
        "selected_agents": ["LifestyleAgent"],
        "selected_capabilities": ["NutritionAgent"],
        "agent_trace": [],
        "errors": [],
        "call_counts": {},
        "safety_result": {"risk_level": "low"},
        "dependencies": deps,
    }

    next_state = response_composer_agent(state)

    assert len(llm_prompts) == 1
    assert next_state["final_answer"] == "Câu trả lời tổng hợp từ mock LLM."


def test_web_search_agent_isolated_execution_with_injected_tavily_fn():
    """Verify web_search_agent uses injected tavily_fn without monkeypatch."""
    web_queries = []

    def mock_tavily(query: str, **kw) -> Optional[str]:
        web_queries.append(query)
        return "Kết quả tìm kiếm web cập nhật: Nghiên cứu dinh dưỡng 2026."

    deps = AgentDependencies(tavily_fn=mock_tavily)

    state: AgentState = {
        "question": "Nghiên cứu mới nhất về whey protein",
        "selected_agents": ["WebSearchAgent"],
        "agent_trace": [],
        "errors": [],
        "call_counts": {},
        "dependencies": deps,
    }

    next_state = web_search_agent(state)

    assert len(web_queries) == 1
    assert web_queries[0] == "Nghiên cứu mới nhất về whey protein"
    assert any(tool["tool"] == "tavily_search_health" for tool in next_state.get("tool_results", []))

import time

from agents import graph


def _must_not_run(name):
    def fail(*args, **kwargs):
        raise AssertionError(f"{name} must not run on this fast path")

    return fail


def _block_llm_and_retrieval(monkeypatch):
    monkeypatch.setattr(
        graph,
        "openai_chat_complete",
        _must_not_run("openai_chat_complete"),
    )
    monkeypatch.setattr(
        graph,
        "vietnamese_llm_chat_complete",
        _must_not_run("vietnamese_llm_chat_complete"),
    )
    monkeypatch.setattr(
        graph,
        "rewrite_query_to_multi_queries",
        _must_not_run("rewrite_query_to_multi_queries"),
    )
    monkeypatch.setattr(graph, "hybrid_search", _must_not_run("hybrid_search"))
    monkeypatch.setattr(
        graph,
        "rerank_documents",
        _must_not_run("rerank_documents"),
    )


def test_urgent_safety_returns_without_llm_or_retrieval(monkeypatch):
    _block_llm_and_retrieval(monkeypatch)

    result = graph.multi_agent_handle(
        "Tôi đau ngực và khó thở khi tập. Tôi có nên tiếp tục không?"
    )

    assert result["status"] == "ok"
    assert result["fast_path"] == "urgent_safety"
    assert result["selected_agents"] == [graph.SAFETY_AGENT]
    assert result["safety_result"]["risk_level"] == "urgent"
    assert "dừng tập ngay" in result["content"].lower()
    assert result["retrieved_docs"] == []
    assert result["errors"] == []


def test_bmi_returns_without_llm_or_retrieval(monkeypatch):
    _block_llm_and_retrieval(monkeypatch)

    result = graph.multi_agent_handle(
        "Tôi nặng 72kg, cao 170cm. Tính BMI giúp tôi."
    )

    assert result["status"] == "ok"
    assert result["fast_path"] == "inbody_tools"
    assert result["selected_agents"] == [graph.INBODY_AGENT]
    assert result["tool_results"][0]["result"]["bmi"] == 24.91
    assert "24.91" in result["content"]
    assert result["retrieved_docs"] == []
    assert result["errors"] == []


def test_greeting_returns_without_llm_or_retrieval(monkeypatch):
    _block_llm_and_retrieval(monkeypatch)

    result = graph.multi_agent_handle("Xin chào, bạn có thể giúp gì cho tôi?")

    assert result["status"] == "ok"
    assert result["fast_path"] == "general_chat"
    assert result["selected_agents"] == [graph.GENERAL_CHAT_AGENT]
    assert "BMI" in result["content"]
    assert result["retrieved_docs"] == []
    assert result["errors"] == []


def test_supervisor_matches_unaccented_training_query():
    state = {
        "question": "Goi y lich tap khang luc 3 buoi/tuan",
        "history": [],
        "agent_trace": [],
        "errors": [],
    }

    result = graph.supervisor_agent(state)

    assert graph.TRAINING_AGENT in result["selected_agents"]
    assert graph.GENERAL_CHAT_AGENT not in result["selected_agents"]


def test_unaccented_measurements_are_parsed_for_bmi(monkeypatch):
    _block_llm_and_retrieval(monkeypatch)

    result = graph.multi_agent_handle(
        "Toi nang 72kg, cao 170cm. Tinh BMI giup toi."
    )

    assert result["fast_path"] == "inbody_tools"
    assert result["tool_results"][0]["result"]["bmi"] == 24.91


def test_rag_uses_original_query_once_by_default(monkeypatch):
    captured = []
    monkeypatch.setattr(graph, "RAG_MAX_RETRIEVAL_QUERIES", 1)
    monkeypatch.setattr(
        graph,
        "rewrite_query_to_multi_queries",
        _must_not_run("rewrite_query_to_multi_queries"),
    )

    def fake_search(query, **kwargs):
        captured.append((query, kwargs))
        return []

    monkeypatch.setattr(graph, "hybrid_search", fake_search)
    state = {
        "question": "BMI và PBF khác nhau thế nào?",
        "selected_agents": [graph.RAG_AGENT],
        "deadline_monotonic": time.monotonic() + 30,
        "agent_trace": [],
        "errors": [],
    }

    result = graph.rag_agent(state)

    assert len(captured) == 1
    assert captured[0][0] == state["question"]
    assert 0 < captured[0][1]["embedding_timeout"] <= 10
    assert result["retrieved_docs"] == []


def test_composer_skips_llm_after_request_deadline(monkeypatch):
    monkeypatch.setattr(
        graph,
        "openai_chat_complete",
        _must_not_run("openai_chat_complete"),
    )
    state = {
        "question": "Giải thích PBF",
        "selected_agents": [graph.RAG_AGENT],
        "deadline_monotonic": time.monotonic() - 1,
        "retrieved_docs": [],
        "tool_results": [],
        "safety_result": {"risk_level": "low"},
        "agent_trace": [],
        "errors": [],
    }

    result = graph.response_composer_agent(state)

    assert result["final_answer"]
    assert "MVP" not in result["final_answer"]
    assert "Kết quả công cụ" not in result["final_answer"]
    assert any("deadline exhausted" in error for error in result["errors"])
    assert result["agent_trace"][-1]["status"] == "warning"

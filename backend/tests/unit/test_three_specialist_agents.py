"""Public contract for the three specialist groups in the monolith graph."""

import pytest

from agents import graph


PUBLIC_SPECIALISTS = {"InBodyAgent", "LifestyleAgent", "KnowledgeAgent"}


def test_graph_has_exactly_three_specialist_nodes():
    compiled = graph._build_graph()
    if compiled is None:
        pytest.skip("LangGraph is not installed")
    nodes = set(compiled.get_graph().nodes)
    assert {"inbody_specialist", "lifestyle_specialist", "knowledge_specialist"} <= nodes
    assert not {"nutrition_agent", "training_agent", "rag_agent", "web_search_agent", "general_chat_agent"} & nodes
    assert [item["name"] for item in graph.get_multi_agent_summary()["agents"]] == [
        "InBodyAgent", "LifestyleAgent", "KnowledgeAgent",
    ]


@pytest.mark.parametrize("question, expected, capabilities", [
    ("Tính BMI từ 72 kg và 170 cm, giải thích PBF", {"InBodyAgent", "KnowledgeAgent"},
     {graph.INBODY_AGENT, graph.RAG_AGENT}),
    ("Gợi ý thực đơn và lịch tập 3 buổi/tuần", {"LifestyleAgent"},
     {graph.NUTRITION_AGENT, graph.TRAINING_AGENT}),
    ("Tin tức sức khỏe mới nhất hôm nay", {"KnowledgeAgent"}, {graph.WEB_SEARCH_AGENT}),
])
def test_router_exposes_only_three_specialists_without_losing_capabilities(question, expected, capabilities):
    state = {"question": question, "agent_trace": [], "errors": []}
    result = graph.supervisor_agent(state)
    assert set(result["selected_agents"]) == expected
    assert set(result["selected_capabilities"]) >= capabilities
    assert set(result["selected_agents"]) <= PUBLIC_SPECIALISTS


def test_caution_disables_lifestyle_and_web_but_keeps_safety_retrieval():
    state = {"question": "Tôi đang dùng thuốc huyết áp, nên tập thế nào?",
             "safety_result": {"risk_level": "medical_caution"}, "agent_trace": [], "errors": []}
    result = graph.supervisor_agent(state)
    assert result["selected_agents"] == ["KnowledgeAgent"]
    assert result["selected_capabilities"] == [graph.RAG_AGENT]


def test_fast_paths_expose_only_specialists_and_preserve_urgent_bypass(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Urgent and BMI must not call retrieval or LLM")
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    monkeypatch.setattr(graph, "openai_chat_complete", forbidden)
    monkeypatch.setattr(graph, "vietnamese_llm_chat_complete", forbidden)
    urgent = graph.multi_agent_handle("Tôi đau ngực và khó thở")
    bmi = graph.multi_agent_handle("Tính BMI giúp tôi: 72 kg, 170 cm")
    assert urgent["fast_path"] == "urgent_safety"
    assert urgent["selected_agents"] == []
    assert urgent["safety_result"]["risk_level"] == "urgent"
    assert bmi["fast_path"] == "inbody_tools"
    assert bmi["selected_agents"] == ["InBodyAgent"]

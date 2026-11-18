"""FIX-02: greetings never hide requests or downgrade medical caution."""

import time

import pytest
from fastapi.testclient import TestClient

from agents import fast_paths, graph
from agents.nodes import supervisor as router
from agents.nodes import normalize
from api import app as api
from health.tools import check_medical_safety
from memory import chat


def forbidden(*args, **kwargs):
    pytest.fail("Unexpected provider, storage, queue, or tool call")


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    for name in ("openai_chat_complete", "vietnamese_llm_chat_complete",
                 "rewrite_query_to_multi_queries", "tavily_search_health"):
        monkeypatch.setattr(graph, name, forbidden)
    monkeypatch.setattr(graph, "RAG_MAX_RETRIEVAL_QUERIES", 1)
    monkeypatch.setattr(router, "detect_route", forbidden)
    monkeypatch.setattr(chat.profiles, "safe_build_confirmed_context",
                        lambda subject: {"available": False})


@pytest.mark.parametrize("question", [
    "Xin chào, bạn có thể giúp gì cho tôi?", "Xin chào!", "Hi", "Hello bạn!",
    "Cảm ơn bạn nhiều!", "Bạn là ai?", "Bạn giúp được gì?",
])
def test_pure_greetings_keep_zero_provider_fast_path(isolated, monkeypatch, question):
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    result = graph.multi_agent_handle(question)
    assert result["fast_path"] == "general_chat"
    assert result["selected_agents"] == [graph.KNOWLEDGE_AGENT]
    assert result["errors"] == []


@pytest.mark.parametrize("question", [
    "Xin chào, tính BMI 72kg 170cm", "Cảm ơn, tính BMI 72kg 170cm giúp tôi",
    "Hello, BMI của tôi: 72kg 170cm", "Chào bạn, BMI 72kg 170cm",
])
def test_greeting_plus_bmi_keeps_calculation(isolated, monkeypatch, question):
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    result = graph.multi_agent_handle(question)
    assert result["fast_path"] == "inbody_tools"
    assert result["tool_results"][0]["result"]["bmi"] == 24.91
    assert result["selected_agents"] == [graph.INBODY_AGENT]
    assert result["errors"] == []


@pytest.mark.parametrize("question", [
    "Cảm ơn, gợi ý dinh dưỡng cho tôi", "Xin chào, gợi ý lịch tập 3 buổi/tuần",
    "Bạn là ai? Giải thích PBF giúp tôi",
])
def test_substantive_request_reaches_specialist_with_original_question(isolated, monkeypatch, question):
    captured = []
    monkeypatch.setattr(graph, "hybrid_search", lambda query, **kw: captured.append(query) or [])
    # A normal plan request may use the composer; only the greeting shortcut
    # must stay provider-free. Keep this provider deterministic and offline.
    monkeypatch.setattr(graph, "openai_chat_complete",
                        lambda *a, **kw: "Bạn vui lòng cung cấp thêm mục tiêu và kinh nghiệm tập luyện.")
    result = graph.multi_agent_handle(question)
    assert result["fast_path"] != "general_chat"
    assert graph.GENERAL_CHAT_AGENT not in result["selected_capabilities"]
    assert set(result["selected_agents"]) <= {graph.INBODY_AGENT, graph.LIFESTYLE_AGENT, graph.KNOWLEDGE_AGENT}
    if graph.RAG_AGENT in result["selected_capabilities"]:
        assert captured == [question]


@pytest.mark.parametrize("question, profile", [
    ("Xin chào, tôi bị tiểu đường, nên dùng liều thuốc nào?", {}),
    ("Xin chào, tôi có bệnh nền", {}),
    ("Tôi đang dùng thuốc, tính BMI 72kg 170cm", {}),
    ("Xin chào!", {"available": True, "profile": {"medical_conditions": ["tăng huyết áp"]}}),
    ("BMI 72kg 170cm", {"available": True, "profile": {"medical_conditions": ["tiểu đường"]}}),
])
def test_caution_skips_low_risk_templates_and_retains_action(isolated, monkeypatch, question, profile):
    captured = []
    monkeypatch.setattr(graph, "hybrid_search", lambda query, **kw: captured.append((query, kw)) or [])
    monkeypatch.setattr(fast_paths, "calculate_bmi", forbidden)
    result = graph.multi_agent_handle(question, user_profile=profile)
    assert result["safety_result"]["risk_level"] == "medical_caution"
    assert result["fast_path"] is None
    assert result["selected_agents"] == [graph.KNOWLEDGE_AGENT]
    assert result["selected_capabilities"] == [graph.RAG_AGENT]
    assert result["safety_result"]["recommended_action"] in result["content"]
    assert result["tool_results"] == []
    assert result["evidence"] == []
    assert len(captured) == 1
    assert captured[0][0] == question
    assert captured[0][1]["filters"] == {"content_type": "medical_safety"}
    risk_traces = [item["summary"] for item in result["agent_trace"] if "Safety risk level:" in item["summary"]]
    assert risk_traces
    assert all("medical_caution" in summary for summary in risk_traces)


@pytest.mark.parametrize("endpoint", ["/agent/answer", "/chat/complete"])
@pytest.mark.parametrize("question, expected", [
    ("Xin chào, tính BMI 72kg 170cm", "inbody_tools"),
    ("Xin chào, tôi bị tiểu đường, hỏi liều thuốc", None),
])
def test_http_contract_for_mixed_greeting(isolated, monkeypatch, endpoint, question, expected):
    monkeypatch.setattr(graph, "hybrid_search", lambda *args, **kwargs: [])
    body = {"question": question} if endpoint == "/agent/answer" else {"user_message": question, "sync_request": True}
    response = TestClient(api.app).post(endpoint, headers={"X-Dev-User-Id": "synthetic-fix02"}, json=body)
    assert response.status_code == 200
    result = response.json() if endpoint == "/agent/answer" else response.json()["response"]
    assert result["fast_path"] == expected
    if expected is None:
        answer = result["answer"] if endpoint == "/agent/answer" else result["content"]
        assert result["safety_result"]["recommended_action"] in answer
    else:
        assert result["tool_results"][0]["result"]["bmi"] == 24.91


@pytest.mark.parametrize("endpoint, sync", [("/agent/answer", True), ("/chat/complete", True), ("/chat/complete", False)])
def test_greeting_urgent_invalid_bypasses_storage_and_queue(isolated, monkeypatch, endpoint, sync):
    monkeypatch.setattr(chat.profiles, "safe_build_confirmed_context", forbidden)
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    monkeypatch.setattr(normalize, "detect_user_intent", forbidden)
    for name in ("create_task", "load_history", "open_conversation", "record_turn"):
        monkeypatch.setattr(chat.store, name, forbidden)
    monkeypatch.setattr(api.llm_handle_message, "apply_async", forbidden, raising=False)
    question = "Xin chào, tôi đau ngực và khó thở, BMI -72kg 170cm"
    body = {"question": question} if endpoint == "/agent/answer" else {"user_message": question, "sync_request": sync}
    response = TestClient(api.app).post(endpoint, headers={"X-Dev-User-Id": "synthetic-fix02"}, json=body)
    assert response.status_code == 200
    result = response.json() if endpoint == "/agent/answer" else response.json()["response"]
    assert result["fast_path"] == "urgent_safety"
    answer = result["answer"] if endpoint == "/agent/answer" else result["content"]
    assert "dừng tập ngay" in answer


def test_greeting_urgent_with_saved_condition_still_bypasses_graph(isolated, monkeypatch):
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    monkeypatch.setattr(normalize, "detect_user_intent", forbidden)
    result = graph.multi_agent_handle("Xin chào, tôi đau ngực và khó thở", user_profile={
        "available": True, "profile": {"medical_conditions": ["tăng huyết áp"]}})
    assert result["fast_path"] == "urgent_safety"
    assert result["safety_result"]["risk_level"] == "urgent"
    assert result["selected_agents"] == []
    assert "dừng tập ngay" in result["content"]


def test_caution_retrieval_failure_still_includes_action(isolated, monkeypatch):
    def unavailable(*a, **kw):
        raise RuntimeError("synthetic retrieval unavailable")
    monkeypatch.setattr(graph, "hybrid_search", unavailable)
    result = graph.multi_agent_handle("Xin chào, tôi đang dùng thuốc, nên ăn và tập thế nào?")
    assert result["status"] == "degraded"
    assert result["selected_agents"] == [graph.KNOWLEDGE_AGENT]
    assert result["safety_result"]["recommended_action"] in result["content"]
    assert result["evidence"] == []


@pytest.mark.parametrize("failure", ["no_evidence", "deadline", "provider", "unsafe_output"])
def test_caution_composer_keeps_action_on_every_exit(isolated, monkeypatch, failure):
    safety = check_medical_safety("Tôi đang dùng thuốc")
    provider_calls = []
    state = {"question": "Tôi đang dùng thuốc", "selected_capabilities": [graph.RAG_AGENT],
             "safety_result": safety, "agent_trace": [], "errors": [], "tool_results": [],
             "retrieved_docs": [], "deadline_monotonic": time.monotonic() + 30}
    if failure in {"provider", "unsafe_output"}:
        from rag.provenance import compute_document_content_hash

        safety_text = "Hỏi bác sĩ khi dùng thuốc."
        safety_hash = compute_document_content_hash(safety_text)
        state["retrieved_docs"] = [
            {
                "document_id": "synthetic-safety",
                "source": "fixture",
                "title": "Thận trọng",
                "content": safety_text,
                "content_type": "medical_safety",
                "document_content_hash": safety_hash,
                "medical_review_status": "approved",
                "review_verification_status": "verified",
                "review_id": "rev-test-caution-001",
                "reviewer_id": "reviewer-test-001",
                "review_scope": "medical_safety",
                "reviewed_at": "2026-11-18T00:00:00Z",
                "reviewed_content_hash": safety_hash,
            }
        ]
        monkeypatch.setattr(graph, "rerank_documents", lambda docs, *a, **k: docs)
        def compose(*a, **kw):
            provider_calls.append(True)
            if failure == "provider":
                raise RuntimeError("synthetic provider unavailable")
            return "Hãy tăng liều thuốc."
        monkeypatch.setattr(graph, "openai_chat_complete", compose)
    if failure == "deadline":
        state["deadline_monotonic"] = time.monotonic() - 1
    result = graph.response_composer_agent(state)
    assert safety["recommended_action"] in result["final_answer"]
    assert result["evidence"] == []
    if failure in {"provider", "unsafe_output"}:
        assert provider_calls


def test_graph_failure_preserves_caution_from_confirmed_profile(isolated, monkeypatch):
    class BrokenGraph:
        def invoke(self, state):
            raise RuntimeError("synthetic graph failure")
    monkeypatch.setattr(graph, "_COMPILED_GRAPH", BrokenGraph())
    monkeypatch.setattr(graph, "StateGraph", object())
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    result = graph.multi_agent_handle("Giải thích PBF", user_profile={
        "available": True, "profile": {"medical_conditions": ["tiểu đường"]}})
    assert result["status"] == "degraded"
    assert result["safety_result"]["risk_level"] == "medical_caution"
    assert result["safety_result"]["recommended_action"] in result["content"]

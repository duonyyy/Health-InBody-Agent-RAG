import os

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("AUTH_MODE", "development")

from api.app import app


client = TestClient(app)
AUTH_HEADERS = {"X-Dev-User-Id": "integration-fast-path-user"}


def test_negative_bmi_input_returns_validation_error():
    response = client.post(
        "/tools/bmi",
        json={"weight_kg": -72, "height_cm": 170},
    )

    assert response.status_code == 422


def test_agent_urgent_contract_exposes_fast_path_and_safety():
    response = client.post(
        "/agent/answer",
        headers=AUTH_HEADERS,
        json={
            "question": "Tôi đau ngực và khó thở khi tập.",
            "history": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["fast_path"] == "urgent_safety"
    assert payload["safety_result"]["risk_level"] == "urgent"
    assert payload["latency_ms"] >= 0
    assert payload["errors"] == []


def test_agent_bmi_contract_exposes_tool_result():
    response = client.post(
        "/agent/answer",
        headers=AUTH_HEADERS,
        json={
            "question": "Tôi nặng 72kg, cao 170cm. BMI của tôi là bao nhiêu?",
            "history": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fast_path"] == "inbody_tools"
    assert payload["tool_results"][0]["result"]["bmi"] == 24.91


def test_urgent_api_bypasses_provider_retrieval_and_review(monkeypatch):
    from agents import composer, graph
    from rag import provenance
    from rag.qdrant import client as qdrant_client

    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("urgent path reached dependency")

    for name in ("openai_chat_complete", "vietnamese_llm_chat_complete", "rewrite_query_to_multi_queries", "hybrid_search", "rerank_documents", "tavily_search_health"):
        monkeypatch.setattr(graph, name, forbidden)
    monkeypatch.setattr(qdrant_client, "search_vector", forbidden)
    monkeypatch.setattr(provenance, "load_review_registry", forbidden)
    monkeypatch.setattr(composer, "prepare_composer_context", forbidden)
    for question in ("Tôi đau ngực và khó thở.", "Toi dau nguc va kho tho."):
        response = client.post("/agent/answer", headers=AUTH_HEADERS, json={"question": question, "history": []})
        assert response.status_code == 200
        payload = response.json()
        assert payload["fast_path"] == "urgent_safety"
        assert payload["safety_result"]["risk_level"] == "urgent"
        assert "dừng tập ngay" in payload["answer"].lower()
        assert "liên hệ" in payload["answer"].lower() and "cấp cứu" in payload["answer"].lower()
        assert payload.get("claim_evidence_links", []) == [] and payload.get("evidence", []) == []
    assert calls == []

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

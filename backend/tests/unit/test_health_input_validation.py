"""FIX-01: preserve explicit metrics and reject invalid input before side effects."""

import pytest
from fastapi.testclient import TestClient

from agents import graph
from agents.parsing import extract_height_cm, extract_pbf, extract_weight_kg
from api import app as api
from memory import chat


def forbidden(*args, **kwargs):
    pytest.fail("Invalid input or urgent safety must not reach storage/provider/queue")


@pytest.mark.parametrize("extract, text, expected", [
    (extract_weight_kg, "-72kg", -72),
    (extract_weight_kg, "−72kg", -72),
    (extract_height_cm, "-170cm", -170),
    (extract_height_cm, "-1m70", -170),
    (extract_height_cm, "170cm", 170),
    (extract_height_cm, "2cm", 2),
    (extract_pbf, "PBF -1%", -1),
])
def test_metric_parser_preserves_sign_and_explicit_unit(extract, text, expected):
    assert extract(text) == expected


@pytest.mark.parametrize("text", ["Tôi muốn giảm 2kg", "Tôi đã giảm -2kg", "Mục tiêu giảm 2kg",
                                 "Mục tiêu 60kg", "Mục tiêu cân nặng là 60kg", "Trước đây tôi nặng 80kg"])
def test_weight_change_is_not_current_weight(text):
    assert extract_weight_kg(text) is None


def test_explicit_current_weight_is_kept_separate_from_history_and_goal():
    assert extract_weight_kg("Trước đây tôi nặng 80kg, hiện tại 72kg, mục tiêu 65kg") == 72


@pytest.mark.parametrize("field, value", [("PBF", 0), ("mỡ nội tạng", 0)])
def test_zero_is_valid_for_metrics_whose_schema_allows_zero(field, value):
    from health.validation import validate_health_input
    validate_health_input(f"{field} {value}")


INVALID = ["-72kg, 170cm", "−72kg, 170cm", "0kg, 170cm", "501kg, 170cm",
           "72kg, -1m70", "72kg, -170cm", "72kg, 301cm", "72kg, 2cm",
           "PBF -1%", "PBF 101%", "mỡ nội tạng -1", "mỡ nội tạng 101"]


@pytest.mark.parametrize("endpoint, sync", [("/agent/answer", True), ("/chat/complete", True),
                                           ("/chat/complete", False)])
@pytest.mark.parametrize("metrics", INVALID)
def test_invalid_chat_returns_422_before_storage_or_dispatch(monkeypatch, endpoint, sync, metrics):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setattr(chat.profiles, "safe_build_confirmed_context", forbidden)
    monkeypatch.setattr(api.memory_store, "create_task", forbidden)
    monkeypatch.setattr(api.memory_store, "load_history", forbidden)
    monkeypatch.setattr(api.llm_handle_message, "apply_async", forbidden, raising=False)
    payload = {"question": "Tính giúp tôi: " + metrics} if endpoint == "/agent/answer" else {
        "user_message": "Tính giúp tôi: " + metrics, "sync_request": sync}
    response = TestClient(api.app).post(endpoint, headers={"X-Dev-User-Id": "synthetic-fix01"}, json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert metrics not in response.json()["detail"]


def test_invalid_explicit_value_never_falls_back_to_saved_measurement(monkeypatch):
    from health.validation import InvalidHealthInput
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    monkeypatch.setattr(graph, "openai_chat_complete", forbidden)
    with pytest.raises(InvalidHealthInput):
        graph.multi_agent_handle("BMI -72kg, 170cm", user_profile={
            "available": True, "latest_confirmed_measurement": {"weight_kg": 72, "height_cm": 170}})


@pytest.mark.parametrize("sync", [True, False])
def test_urgent_invalid_input_still_bypasses_storage_and_queue(monkeypatch, sync):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setattr(chat.profiles, "safe_build_confirmed_context", forbidden)
    monkeypatch.setattr(api.memory_store, "create_task", forbidden)
    monkeypatch.setattr(graph, "hybrid_search", forbidden)
    monkeypatch.setattr(graph, "openai_chat_complete", forbidden)
    response = TestClient(api.app).post("/chat/complete", headers={"X-Dev-User-Id": "synthetic-fix01"},
        json={"user_message": "Tôi đau ngực và khó thở, BMI -72kg, 170cm", "sync_request": sync})
    assert response.status_code == 200
    assert response.json()["response"]["fast_path"] == "urgent_safety"


@pytest.mark.parametrize("text", ["Tôi nặng 70kg hoặc 72kg, tính BMI", "Tôi nặng 70-72kg, cao 170cm"])
def test_ambiguous_current_measurement_requests_clarification(text):
    from health.validation import InvalidHealthInput, validate_health_input
    with pytest.raises(InvalidHealthInput, match="xác nhận"):
        validate_health_input(text)


def test_worker_path_rejects_invalid_input_before_database(monkeypatch):
    from health.validation import InvalidHealthInput
    monkeypatch.setattr(chat.profiles, "safe_build_confirmed_context", forbidden)
    with pytest.raises(InvalidHealthInput):
        chat.run_chat("BMI -72kg, 170cm", "synthetic-fix01")


def test_missing_height_does_not_invent_bmi():
    assert graph._try_inbody_fast_path({"question": "Tính BMI, tôi nặng 72kg"}) is None

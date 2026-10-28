"""Unit tests verifying contracts schemas and serialization for inter-service communication."""

import pytest
from contracts import (
    APIError,
    AgentChatRequest,
    AgentChatResponse,
    BmiRequest,
    BmiResult,
    PersonalizationContext,
    Principal,
    UniformEnvelope,
)


def test_uniform_envelope_ok():
    envelope = UniformEnvelope.ok(data={"status": "active"}, meta={"latency_ms": 15.2})
    assert envelope.success is True
    assert envelope.data == {"status": "active"}
    assert envelope.error is None
    assert envelope.meta.get("latency_ms") == 15.2
    assert "timestamp" in envelope.meta


def test_uniform_envelope_fail():
    envelope = UniformEnvelope.fail(
        code="UNAUTHORIZED",
        message="Invalid token",
        details={"ip": "127.0.0.1"},
        meta={"request_id": "req-123"},
    )
    assert envelope.success is False
    assert envelope.data is None
    assert envelope.error is not None
    assert envelope.error.code == "UNAUTHORIZED"
    assert envelope.error.message == "Invalid token"
    assert envelope.meta.get("request_id") == "req-123"


def test_agent_chat_request_serialization():
    principal = Principal(user_id="user-001", role="patient")
    req = AgentChatRequest(
        principal=principal,
        question="Chỉ số BMI của tôi là bao nhiêu nếu 70kg và 1m75?",
        personalization_context=PersonalizationContext(available=True, gender="male"),
    )
    data = req.model_dump()
    assert data["principal"]["user_id"] == "user-001"
    assert data["question"].startswith("Chỉ số BMI")
    assert data["personalization_context"]["available"] is True


def test_agent_chat_response_contract():
    resp = AgentChatResponse(
        answer="BMI của bạn là 22.86 kg/m².",
        status="ok",
        selected_agents=["InBodyAgent", "ResponseComposer"],
        tool_results=[{"tool": "calculate_bmi", "result": {"bmi": 22.86}}],
        latency_ms=310.5,
    )
    assert resp.status == "ok"
    assert len(resp.selected_agents) == 2
    assert resp.latency_ms == 310.5

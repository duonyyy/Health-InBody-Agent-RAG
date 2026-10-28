"""Unit tests for Core Business API endpoints and BFF functionality."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from config import settings
from contracts.agent import AgentChatResponse
from contracts.envelope import UniformEnvelope
from main import app

client = TestClient(app)


def test_core_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["service"] == "health-core-api"
    assert data["data"]["status"] == "healthy"


def test_core_api_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Health Core Business API (BFF)"


def test_me_profile_unauthorized_when_no_auth():
    response = client.get("/me/profile")
    # In development mode without header, defaults or 401
    assert response.status_code in {200, 401}


def test_chat_complete_bff_flow():
    mock_agent_response = UniformEnvelope.ok(
        data=AgentChatResponse(
            answer="Chỉ số BMI của bạn hoàn toàn bình thường.",
            status="ok",
            selected_agents=["InBodyAgent"],
            latency_ms=120.0,
        )
    )

    with patch("api.routes.chat.agent_client.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_agent_response

        headers = {"X-Dev-User-Id": "test-user-123"}
        payload = {
            "user_message": "Chỉ số BMI của tôi thế nào?",
            "bot_id": "health-inbody-agent",
        }
        response = client.post("/chat/complete", json=payload, headers=headers)
        assert response.status_code == 200
        res_data = response.json()
        assert "response" in res_data
        assert res_data["response"]["content"] == "Chỉ số BMI của bạn hoàn toàn bình thường."
        assert res_data["response"]["status"] == "ok"
        assert mock_chat.called

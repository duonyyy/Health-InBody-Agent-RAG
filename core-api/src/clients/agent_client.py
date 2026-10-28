"""HTTP Client for communicating with the Agentic AI Platform service."""

import logging
from typing import Optional
import httpx

from config import settings
from contracts.agent import AgentChatRequest, AgentChatResponse
from contracts.envelope import UniformEnvelope

logger = logging.getLogger(__name__)


class AgentServiceClient:
    """Async client managing HTTP communication with agent-service."""

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: Optional[int] = None):
        self.base_url = (base_url or settings.agent_service_url).rstrip("/")
        self.timeout = timeout_seconds or settings.agent_request_timeout

    async def chat(self, request: AgentChatRequest) -> UniformEnvelope[AgentChatResponse]:
        """Send chat request to agent-service and return typed response envelope."""
        url = f"{self.base_url}/v1/agent/chat"
        payload = request.model_dump()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return UniformEnvelope[AgentChatResponse].model_validate(data)
        except httpx.TimeoutException:
            logger.error("Agent service timed out at %s after %ss", url, self.timeout)
            fallback_response = AgentChatResponse(
                answer="Hệ thống trợ lý AI phản hồi quá thời gian quy định. Vui lòng thử lại sau.",
                status="degraded",
                errors=["agent_service_timeout"],
            )
            return UniformEnvelope.ok(
                data=fallback_response,
                meta={"request_id": request.request_id, "fallback": True},
            )
        except Exception as exc:
            logger.error("Agent service connection failed: %s", exc)
            fallback_response = AgentChatResponse(
                answer="Dịch vụ phân tích AI tạm thời gián đoạn kết nối. Vui lòng kiểm tra lại sau.",
                status="error",
                errors=[str(exc)],
            )
            return UniformEnvelope.ok(
                data=fallback_response,
                meta={"request_id": request.request_id, "fallback": True},
            )

    async def health(self) -> dict:
        """Ping agent service health endpoint."""
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.json()
        except Exception as exc:
            return {"status": "unreachable", "error": str(exc)}


agent_client = AgentServiceClient()

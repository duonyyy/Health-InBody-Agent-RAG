"""BFF Chat routes forwarding client requests to agent-service."""

import logging
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.context import CurrentUser, get_current_user
from clients.agent_client import agent_client
from contracts.agent import (
    AgentChatRequest,
    AgentChatResponse,
    HistoryTurn,
    PersonalizationContext,
    Principal,
)
from persistence.models import update_chat_conversation
from persistence.personalization_service import safe_build_confirmed_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class HistoryTurnPayload(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class CompleteRequest(BaseModel):
    bot_id: str = Field(default="health-inbody-agent", max_length=128)
    user_id: Optional[str] = Field(default=None, min_length=1)
    user_message: str = Field(min_length=1, max_length=4000)
    history: Optional[List[HistoryTurnPayload]] = Field(default=None, max_length=10)
    conversation_id: Optional[UUID] = None
    sync_request: Optional[bool] = True


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: Optional[List[HistoryTurnPayload]] = Field(default=None, max_length=10)
    user_id: Optional[str] = None
    conversation_id: Optional[UUID] = None


@router.post("/chat/complete")
async def chat_complete(data: CompleteRequest, current_user: CurrentUser = Depends(get_current_user)):
    """BFF Endpoint: Authenticates user, loads profile & latest InBody, calls agent-service."""
    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    start_time = time.perf_counter()

    # 1. Load user confirmed personalization context from PostgreSQL
    raw_context = safe_build_confirmed_context(current_user.subject)
    pers_context = PersonalizationContext(
        available=bool(raw_context.get("available")),
        gender=(raw_context.get("profile") or {}).get("sex"),
        birth_year=(raw_context.get("profile") or {}).get("birth_year"),
        medical_conditions=(raw_context.get("profile") or {}).get("medical_conditions", "").split(",") if (raw_context.get("profile") or {}).get("medical_conditions") else [],
        latest_measurement=raw_context.get("latest_confirmed_measurement"),
        reason=raw_context.get("reason"),
        provenance=raw_context.get("provenance") or [],
    )

    # 2. Convert history to typed contract
    history_contract = []
    if data.history:
        for turn in data.history:
            history_contract.append(HistoryTurn(role=turn.role, content=turn.content))

    # 3. Construct unified inter-service AgentChatRequest
    agent_req = AgentChatRequest(
        principal=Principal(user_id=current_user.subject, role="authenticated_user"),
        question=data.user_message,
        history=history_contract,
        personalization_context=pers_context,
        conversation_id=str(data.conversation_id) if data.conversation_id else None,
    )

    # 4. Invoke agent-service via HTTP
    envelope = await agent_client.chat(agent_req)
    agent_resp: AgentChatResponse = envelope.data

    # 5. Persist turn into PostgreSQL
    try:
        update_chat_conversation(data.bot_id, current_user.subject, data.user_message, is_user=True)
        update_chat_conversation(data.bot_id, current_user.subject, agent_resp.answer, is_user=False)
    except Exception as exc:
        logger.warning("Could not persist conversation turn to DB: %s", exc)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 6. Return response in Frontend-compatible envelope
    return {
        "response": {
            "role": "assistant",
            "content": agent_resp.answer,
            "status": agent_resp.status,
            "fast_path": agent_resp.fast_path,
            "selected_agents": agent_resp.selected_agents,
            "agent_trace": [t.model_dump() for t in agent_resp.agent_trace],
            "tool_results": agent_resp.tool_results,
            "retrieved_docs": agent_resp.retrieved_docs,
            "evidence": agent_resp.evidence,
            "claim_evidence_links": agent_resp.claim_evidence_links,
            "evidence_status": agent_resp.evidence_status,
            "safety_result": agent_resp.safety_result,
            "errors": agent_resp.errors,
            "latency_ms": latency_ms,
        }
    }


@router.post("/agent/answer")
async def agent_answer(data: AgentRequest, current_user: CurrentUser = Depends(get_current_user)):
    """Direct agent query endpoint."""
    complete_req = CompleteRequest(
        user_id=data.user_id,
        user_message=data.question,
        history=data.history,
        conversation_id=data.conversation_id,
    )
    result = await chat_complete(complete_req, current_user)
    resp = result["response"]
    return {
        "answer": resp["content"],
        "conversation_id": str(data.conversation_id) if data.conversation_id else None,
        "status": resp["status"],
        "fast_path": resp["fast_path"],
        "latency_ms": resp["latency_ms"],
        "agent_trace": resp["agent_trace"],
        "selected_agents": resp["selected_agents"],
        "tool_results": resp["tool_results"],
        "retrieved_docs": resp["retrieved_docs"],
        "citations": resp["evidence"],
        "claim_evidence_links": resp["claim_evidence_links"],
        "evidence_status": resp["evidence_status"],
        "safety_result": resp["safety_result"],
        "errors": resp["errors"],
    }


@router.get("/agent/tools")
async def agent_tools():
    """Proxy agent tools schema info from agent-service."""
    health_info = await agent_client.health()
    return {
        "domain": "health_inbody",
        "orchestration": "Agentic AI Platform (Microservice)",
        "agent_service": health_info,
    }

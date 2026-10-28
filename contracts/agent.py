"""Agent contracts: Pydantic schemas for core-api <-> agent-service interaction."""

import uuid
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Principal(BaseModel):
    """Immutable identity context passed from core-api gatekeeper to agent-service."""
    user_id: str = Field(..., description="Unique user identifier from auth context")
    role: str = Field(default="authenticated_user", description="RBAC role, e.g., user, admin")
    tenant_id: str = Field(default="default", description="Multi-tenant identifier")


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class PersonalizationContext(BaseModel):
    available: bool = False
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    medical_conditions: List[str] = Field(default_factory=list)
    latest_measurement: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    provenance: List[str] = Field(default_factory=list)


class AgentChatRequest(BaseModel):
    """The unified request payload sent from core-api to agent-service."""
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    principal: Principal
    question: str = Field(..., min_length=1, max_length=4000)
    history: List[HistoryTurn] = Field(default_factory=list, max_length=15)
    personalization_context: Optional[PersonalizationContext] = None
    conversation_id: Optional[str] = None
    stream: bool = False
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class AgentTraceItem(BaseModel):
    agent: str
    action: str
    status: Literal["success", "warning", "error", "skipped"]
    latency_ms: Optional[float] = None
    detail: Optional[str] = None


class AgentEvidenceItem(BaseModel):
    source: str
    title: Optional[str] = None
    content: str
    confidence: Optional[float] = None


class AgentChatResponse(BaseModel):
    """The structured agent response contract matching AGENTS.md requirements."""
    answer: str
    status: Literal["ok", "degraded", "error"] = "ok"
    fast_path: Optional[str] = None
    selected_agents: List[str] = Field(default_factory=list)
    agent_trace: List[AgentTraceItem] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_docs: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    claim_evidence_links: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_status: str = "not_required"
    safety_result: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0

"""API routes for Agentic AI Platform service."""

import logging
import time
from fastapi import APIRouter, HTTPException

from agents import get_multi_agent_summary, multi_agent_handle
from contracts.agent import AgentChatRequest, AgentChatResponse, AgentTraceItem
from contracts.envelope import UniformEnvelope
from contracts.health import (
    BmiRequest,
    BmiResult,
    NutritionRequest,
    PbfRequest,
    SafetyRequest,
    TrainingRequest,
    VisceralFatRequest,
)
from core.cache import cache_health_check
from guards.injection import PromptInjectionDetector
from guards.sanitizer import InputSanitizer
from health.tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from llm.client import get_llm_runtime_config
from rag.search import get_search_stats, hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/agent/chat", response_model=UniformEnvelope[AgentChatResponse])
async def agent_chat(request: AgentChatRequest):
    """
    Core Entrypoint for AI Multi-Agent reasoning.
    Executes:
    1. Input sanitization & Prompt Injection detection.
    2. Deterministic safety check (Fast-path if urgent).
    3. LangGraph Orchestrator (supervisor -> specialists -> composer).
    """
    start_time = time.perf_counter()

    # 1. Sanitize input & Check Injection
    cleaned_question = InputSanitizer.sanitize(request.question)
    if PromptInjectionDetector.is_injection(cleaned_question):
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response_data = AgentChatResponse(
            answer="Yêu cầu của bạn bị từ chối do vi phạm quy chuẩn an toàn bảo mật hệ thống.",
            status="error",
            fast_path="prompt_injection_guard",
            latency_ms=latency_ms,
        )
        return UniformEnvelope.ok(
            data=response_data,
            meta={"request_id": request.request_id, "latency_ms": latency_ms},
        )

    # 2. Extract personalization context
    pers_dict = {}
    if request.personalization_context:
        pers_dict = request.personalization_context.model_dump()

    # Convert history
    history_payload = [h.model_dump() for h in request.history]

    # 3. Call multi_agent_handle
    result = multi_agent_handle(
        question=cleaned_question,
        history=history_payload,
        user_id=request.principal.user_id,
        user_profile=pers_dict,
        conversation_id=request.conversation_id or "main",
    )

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 4. Map trace to typed items
    trace_items = []
    for t in result.get("agent_trace") or []:
        trace_items.append(
            AgentTraceItem(
                agent=t.get("agent", "Agent"),
                action=t.get("action", "run"),
                status=t.get("status", "success"),
                latency_ms=t.get("latency_ms"),
                detail=t.get("detail"),
            )
        )

    response_data = AgentChatResponse(
        answer=result.get("content", ""),
        status=result.get("status", "ok"),
        fast_path=result.get("fast_path"),
        selected_agents=result.get("selected_agents") or [],
        agent_trace=trace_items,
        tool_results=result.get("tool_results") or [],
        retrieved_docs=result.get("retrieved_docs") or [],
        evidence=result.get("evidence") or [],
        claim_evidence_links=result.get("claim_evidence_links") or [],
        evidence_status=result.get("evidence_status", "not_required"),
        safety_result=result.get("safety_result") or {},
        errors=result.get("errors") or [],
        latency_ms=latency_ms,
    )

    return UniformEnvelope.ok(
        data=response_data,
        meta={"request_id": request.request_id, "latency_ms": latency_ms},
    )


# --- HEALTH BIOMETRIC TOOLS ENDPOINTS ---

@router.post("/v1/tools/bmi")
async def bmi_endpoint(data: BmiRequest):
    return calculate_bmi(data.weight_kg, data.height_cm)


@router.post("/v1/tools/pbf")
async def pbf_endpoint(data: PbfRequest):
    return evaluate_body_fat_percentage(data.pbf_percent, data.sex)


@router.post("/v1/tools/visceral-fat")
async def visceral_fat_endpoint(data: VisceralFatRequest):
    return evaluate_visceral_fat(data.visceral_fat_level)


@router.post("/v1/tools/nutrition")
async def nutrition_endpoint(data: NutritionRequest):
    return suggest_nutrition_goal(data.goal, data.weight_kg, data.activity_level)


@router.post("/v1/tools/training")
async def training_endpoint(data: TrainingRequest):
    return suggest_training_plan(data.goal, data.fitness_level, data.days_per_week)


@router.post("/v1/tools/safety")
async def safety_endpoint(data: SafetyRequest):
    return check_medical_safety(data.question, data.conditions)


# --- RAG SEARCH ENDPOINT ---

@router.post("/v1/rag/search")
async def search_endpoint(query: str, limit: int = 5, use_rerank: bool = True):
    return {
        "query": query,
        "results": hybrid_search(query, limit=limit, use_rerank=use_rerank),
    }


# --- HEALTH CHECK & METRICS ---

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "health-agent-service",
        "cache": cache_health_check(),
        "search": get_search_stats(),
        "llm": get_llm_runtime_config(),
        "agent": get_multi_agent_summary(),
    }

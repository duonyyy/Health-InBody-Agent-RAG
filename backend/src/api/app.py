"""FastAPI entrypoint cho Health/InBody Agent RAG backend."""
import logging
import asyncio
import os
import time
from datetime import date
from typing import Any, Dict, List, Optional, Literal
from uuid import UUID

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from agents import get_multi_agent_summary, multi_agent_handle
from llm.client import get_llm_runtime_config
from core.cache import cache_health_check
from core.config import DEFAULT_COLLECTION_NAME, DEFAULT_VECTOR_SIZE
from health.tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from persistence.personalization import (
    add_inbody_measurement,
    get_user_profile,
    list_inbody_measurements,
    upsert_user_profile,
)
from rag.search import (
    get_search_stats,
    hybrid_search,
    initialize_search_index,
    load_search_snapshot,
)
from llm.summarizer import summarize_health_report, summarize_text
from jobs.tasks import index_document_v2, index_health_documents, llm_handle_message
from core.utils import setup_logging
from api.personalization import router as personalization_router
from api.personalization import _execute
from api.memory import router as memory_router
from memory.chat import run_chat
from memory import store as memory_store
from auth.context import CurrentUser, get_current_user, require_legacy_user_match
from auth.context import require_corpus_admin
from rag.corpus_policy import validate_shared_document, require_staging_collection
from persistence.personalization_service import (
    redacted_context,
    safe_build_confirmed_context,
)

setup_logging()
logger = logging.getLogger(__name__)

TASK_TIMEOUT = 60
POLLING_INTERVAL = 0.5

app = FastAPI(
    title="Health/InBody Agent RAG Backend",
    version="1.0.0-beta",
    description=(
        "Backend API cho chatbot Health/InBody RAG: chat, health tools, "
        "hybrid search, indexing và summarization."
    ),
)
app.include_router(personalization_router)
app.include_router(memory_router)


@app.on_event("startup")
def load_bm25_snapshot_on_startup():
    """Load the versioned local BM25 snapshot without blocking dense fallback."""
    if os.getenv("BM25_AUTOLOAD", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info("BM25 snapshot autoload is disabled")
        return
    if not load_search_snapshot():
        logger.warning("BM25 snapshot unavailable; continuing with dense retrieval")


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1500)


class CompleteRequest(BaseModel):
    bot_id: str = Field(default="health-inbody-agent", max_length=128)
    user_id: Optional[str] = Field(default=None, min_length=1)
    user_message: str = Field(min_length=1, max_length=4000)
    # Deprecated compatibility input; never used as server history.
    history: Optional[List[HistoryTurn]] = Field(default=None, max_length=10)
    conversation_id: Optional[UUID] = None
    sync_request: Optional[bool] = True


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: Optional[List[HistoryTurn]] = Field(default=None, max_length=10)
    user_id: Optional[str] = None
    conversation_id: Optional[UUID] = None


def _memory_identity_allowed(current_user: CurrentUser) -> bool:
    return (current_user.auth_source == "server_context"
            or (current_user.auth_source == "development_header"
                and os.getenv("ZEP_ALLOW_DEV_IDENTITY", "false").lower() in {"1", "true", "yes", "on"}))


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = True


class CollectionCreateRequest(BaseModel):
    collection_name: str = DEFAULT_COLLECTION_NAME
    vector_size: int = Field(default=DEFAULT_VECTOR_SIZE, ge=1)


class DocumentCreateRequest(BaseModel):
    id: str
    question: Optional[str] = ""
    content: str = Field(min_length=1, max_length=100000)
    collection_name: str = DEFAULT_COLLECTION_NAME
    metadata: Optional[Dict[str, Any]] = None


class DocumentsIndexRequest(BaseModel):
    documents: List[Dict[str, Any]] = Field(min_length=1, max_length=100)
    collection_name: str = DEFAULT_COLLECTION_NAME


class SummaryRequest(BaseModel):
    text: str
    report_mode: bool = False


class BmiRequest(BaseModel):
    weight_kg: float = Field(gt=0, le=500)
    height_cm: float = Field(ge=30, le=300)


class PbfRequest(BaseModel):
    pbf_percent: float = Field(ge=0, le=100)
    sex: Optional[str] = None


class VisceralFatRequest(BaseModel):
    visceral_fat_level: float = Field(ge=0, le=100)


class NutritionRequest(BaseModel):
    goal: str = "fat_loss"
    weight_kg: float = Field(gt=0, le=500)
    activity_level: str = "moderate"


class TrainingRequest(BaseModel):
    goal: str = "fat_loss"
    fitness_level: str = "beginner"
    days_per_week: int = Field(default=3, ge=1, le=7)


class SafetyRequest(BaseModel):
    question: str = Field(min_length=1)
    conditions: Optional[List[str]] = None


class UserProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    sex: Optional[str] = None
    birth_year: Optional[int] = None
    height_cm: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    medical_conditions: Optional[str] = None


class InBodyMeasurementRequest(BaseModel):
    measurement_date: date
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bmi: Optional[float] = None
    smm_kg: Optional[float] = None
    bfm_kg: Optional[float] = None
    pbf_percent: Optional[float] = None
    visceral_fat_level: Optional[float] = None
    body_water_l: Optional[float] = None
    recommendation_goal: Optional[str] = None
    source_file: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


@app.get("/")
async def root():
    return {
        "service": "Health/InBody Agent RAG Backend",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Health/InBody Agent RAG Backend",
        "cache": cache_health_check(),
        "search": get_search_stats(),
        "llm": get_llm_runtime_config(),
        "agent": get_multi_agent_summary(),
    }


@app.get("/users/{user_id}/profile")
async def user_profile(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    require_legacy_user_match(user_id, current_user)
    try:
        return get_user_profile(user_id, auto_create=True)
    except Exception as e:
        logger.error("Get user profile failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to load user profile")


@app.put("/users/{user_id}/profile")
async def update_user_profile(
    user_id: str,
    data: UserProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    try:
        return upsert_user_profile(user_id, data.dict(exclude_unset=True))
    except Exception as e:
        logger.error("Update user profile failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to update user profile")


@app.get("/users/{user_id}/measurements")
async def user_measurements(
    user_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    try:
        return {"measurements": list_inbody_measurements(user_id, limit=limit)}
    except Exception as e:
        logger.error("List user measurements failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to list user measurements")


@app.post("/users/{user_id}/measurements")
async def create_user_measurement(
    user_id: str,
    data: InBodyMeasurementRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    try:
        return add_inbody_measurement(user_id, data.dict(exclude_unset=True))
    except Exception as e:
        logger.error("Create user measurement failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to create user measurement")


@app.get("/users/{user_id}/personalization-context")
async def user_personalization_context(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    return redacted_context(current_user.subject)


@app.post("/chat/complete")
async def complete(data: CompleteRequest, current_user: CurrentUser = Depends(get_current_user)):
    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info(
        "Chat request received bot_id=%s sync=%s",
        data.bot_id,
        data.sync_request,
    )

    if data.sync_request:
        try:
            request_started = time.perf_counter()
            response = await run_in_threadpool(
                _execute, run_chat,
                data.user_message,
                current_user.subject,
                bot_id=data.bot_id,
                use_zep_memory=_memory_identity_allowed(current_user),
                conversation_id=data.conversation_id,
            )
            response["latency_ms"] = round(
                (time.perf_counter() - request_started) * 1000,
                2,
            )
            return {"response": response}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Chat sync failed (%s)", type(e).__name__)
            raise HTTPException(status_code=500, detail="Unable to complete chat request")

    if not hasattr(llm_handle_message, "apply_async"):
        raise HTTPException(
            status_code=503,
            detail="Celery worker is not available; use sync_request=true",
        )

    if data.conversation_id:
        await run_in_threadpool(_execute, memory_store.load_history, current_user.subject, str(data.conversation_id))
    task_id = await run_in_threadpool(_execute, memory_store.create_task, current_user.subject)
    try:
        await run_in_threadpool(llm_handle_message.apply_async,
            args=[data.bot_id, current_user.subject, data.user_message,
                  str(data.conversation_id) if data.conversation_id else None],
            task_id=task_id, kwargs={"task_id": task_id},
            argsrepr="[redacted chat arguments]", kwargsrepr="{redacted task metadata}")
    except Exception as exc:
        logger.warning("Chat dispatch failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Hàng đợi hội thoại tạm thời không khả dụng") from exc
    return {"task_id": task_id}


@app.get("/chat/complete/{task_id}")
async def get_response(task_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    task_id = str(task_id)
    await run_in_threadpool(_execute, memory_store.require_task_owner, current_user.subject, task_id)
    if AsyncResult is None:
        raise HTTPException(status_code=503, detail="Celery result backend unavailable")

    start_time = time.time()
    while True:
        task_result = AsyncResult(task_id)
        task_status = task_result.status

        if task_status in {"PENDING", "STARTED", "RETRY"}:
            if time.time() - start_time > TASK_TIMEOUT:
                raise HTTPException(status_code=504, detail="Task result timed out; please retry")
            await asyncio.sleep(POLLING_INTERVAL)
            continue

        if task_status != "SUCCESS":
            raise HTTPException(status_code=502, detail="Không thể hoàn thành yêu cầu hội thoại")
        return {
            "task_id": task_id,
            "task_status": task_result.status,
            "task_result": task_result.result,
        }


@app.post("/agent/answer")
async def agent_answer(data: AgentRequest, current_user: CurrentUser = Depends(get_current_user)):
    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")
    request_started = time.perf_counter()
    response = await run_in_threadpool(
        _execute, run_chat,
        data.question,
        current_user.subject,
        use_zep_memory=_memory_identity_allowed(current_user),
        conversation_id=data.conversation_id,
    )
    return {
        "answer": response["content"],
        "conversation_id": response.get("conversation_id"),
        "memory_status": response.get("memory_status"),
        "memory_proposals": response.get("memory_proposals", []),
        "user_message_id": response.get("user_message_id"),
        "status": response.get("status", "ok"),
        "fast_path": response.get("fast_path"),
        "latency_ms": round((time.perf_counter() - request_started) * 1000, 2),
        "agent_trace": response.get("agent_trace", []),
        "selected_agents": response.get("selected_agents", []),
        "tool_results": response.get("tool_results", []),
        "retrieved_docs": response.get("retrieved_docs", []),
        "citations": response.get("evidence", []),
        "claim_evidence_links": response.get("claim_evidence_links", []),
        "evidence_status": response.get("evidence_status", "not_required"),
        "limitations": response.get("limitations", []),
        "safety_result": response.get("safety_result", {}),
        "personalization_used": response.get("personalization_used", {}),
        "errors": response.get("errors", []),
        "agent": get_multi_agent_summary(),
    }


@app.get("/agent/tools")
async def agent_tools():
    return get_multi_agent_summary()


@app.post("/search")
async def search_endpoint(data: SearchRequest):
    return {
        "query": data.query,
        "results": hybrid_search(data.query, limit=data.limit, use_rerank=data.use_rerank),
    }


@app.post("/collection/create")
async def create_vector_collection(data: CollectionCreateRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_corpus_admission(data.collection_name, [])
    try:
        from rag.qdrant.client import create_collection

        create_status = create_collection(data.collection_name, data.vector_size)
        return {"status": create_status is not None, "result": str(create_status)}
    except Exception as e:
        logger.error("Create collection failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to create collection")


@app.post("/document/create")
async def create_document(data: DocumentCreateRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_corpus_admission(data.collection_name, [data.model_dump()])
    try:
        index_status = index_document_v2(
            data.id,
            data.question,
            data.content,
            collection_name=data.collection_name,
            metadata=data.metadata,
        )
        return {"status": True, "index_status": index_status}
    except Exception as e:
        logger.error("Create/index document failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to create or index document")


@app.post("/documents/index")
async def index_documents(data: DocumentsIndexRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_corpus_admission(data.collection_name, data.documents)
    try:
        result = index_health_documents(data.documents, collection_name=data.collection_name)
        return {"status": True, "result": result}
    except Exception as e:
        logger.error("Batch index failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to index documents")


@app.post("/summarize")
async def summarize_endpoint(data: SummaryRequest):
    if data.report_mode:
        return {"summary": summarize_health_report(data.text)}
    return {"summary": summarize_text(data.text)}


@app.post("/tools/bmi")
async def bmi_endpoint(data: BmiRequest):
    return calculate_bmi(data.weight_kg, data.height_cm)


@app.post("/tools/pbf")
async def pbf_endpoint(data: PbfRequest):
    return evaluate_body_fat_percentage(data.pbf_percent, data.sex)


@app.post("/tools/visceral-fat")
async def visceral_fat_endpoint(data: VisceralFatRequest):
    return evaluate_visceral_fat(data.visceral_fat_level)


@app.post("/tools/nutrition")
async def nutrition_endpoint(data: NutritionRequest):
    return suggest_nutrition_goal(data.goal, data.weight_kg, data.activity_level)


@app.post("/tools/training")
async def training_endpoint(data: TrainingRequest):
    return suggest_training_plan(data.goal, data.fitness_level, data.days_per_week)


@app.post("/tools/safety")
async def safety_endpoint(data: SafetyRequest):
    return check_medical_safety(data.question, data.conditions)


@app.post("/data/import")
async def import_data_endpoint(data: DocumentsIndexRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_corpus_admission(data.collection_name, data.documents)
    result = index_health_documents(data.documents, collection_name=data.collection_name)
    return {"success": True, "result": result}


def _validate_corpus_admission(collection_name: str, documents: list) -> None:
    try:
        require_staging_collection(collection_name)
        for document in documents:
            validate_shared_document(document, require_review=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, workers=1, log_level="info")

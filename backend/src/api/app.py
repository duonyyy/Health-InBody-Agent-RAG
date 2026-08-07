"""FastAPI entrypoint cho Health/InBody Agent RAG backend."""
import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

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
    safe_build_personalization_context,
    upsert_user_profile,
)
from rag.search import get_search_stats, hybrid_search, initialize_search_index
from llm.summarizer import summarize_health_report, summarize_text
from jobs.tasks import index_document_v2, index_health_documents, llm_handle_message
from core.utils import setup_logging

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


class CompleteRequest(BaseModel):
    bot_id: Optional[str] = "health-inbody-agent"
    user_id: str = Field(min_length=1)
    user_message: str = Field(min_length=1)
    history: Optional[List[Dict[str, str]]] = None
    sync_request: Optional[bool] = True


class AgentRequest(BaseModel):
    question: str = Field(min_length=1)
    history: Optional[List[Dict[str, str]]] = None
    user_id: Optional[str] = None


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
    content: str
    collection_name: str = DEFAULT_COLLECTION_NAME
    metadata: Optional[Dict[str, Any]] = None


class DocumentsIndexRequest(BaseModel):
    documents: List[Dict[str, Any]]
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
async def user_profile(user_id: str):
    try:
        return get_user_profile(user_id, auto_create=True)
    except Exception as e:
        logger.error("Get user profile failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/users/{user_id}/profile")
async def update_user_profile(user_id: str, data: UserProfileRequest):
    try:
        return upsert_user_profile(user_id, data.dict(exclude_unset=True))
    except Exception as e:
        logger.error("Update user profile failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}/measurements")
async def user_measurements(user_id: str, limit: int = Query(default=5, ge=1, le=50)):
    try:
        return {"measurements": list_inbody_measurements(user_id, limit=limit)}
    except Exception as e:
        logger.error("List user measurements failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/users/{user_id}/measurements")
async def create_user_measurement(user_id: str, data: InBodyMeasurementRequest):
    try:
        return add_inbody_measurement(user_id, data.dict(exclude_unset=True))
    except Exception as e:
        logger.error("Create user measurement failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}/personalization-context")
async def user_personalization_context(user_id: str):
    return safe_build_personalization_context(user_id)


@app.post("/chat/complete")
async def complete(data: CompleteRequest):
    if not data.user_id or not data.user_message:
        raise HTTPException(
            status_code=400,
            detail="user_id and user_message are required",
        )

    logger.info(
        "Chat request user_id=%s bot_id=%s sync=%s",
        data.user_id,
        data.bot_id,
        data.sync_request,
    )

    if data.sync_request:
        try:
            request_started = time.perf_counter()
            personalization_context = safe_build_personalization_context(data.user_id)
            response = multi_agent_handle(
                data.user_message,
                history=data.history,
                user_id=data.user_id,
                user_profile=personalization_context,
            )
            response["latency_ms"] = round(
                (time.perf_counter() - request_started) * 1000,
                2,
            )
            return {"response": response}
        except Exception as e:
            logger.error("Chat sync failed: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    if not hasattr(llm_handle_message, "delay"):
        raise HTTPException(
            status_code=503,
            detail="Celery worker is not available; use sync_request=true",
        )

    task = llm_handle_message.delay(data.bot_id, data.user_id, data.user_message)
    return {"task_id": task.id}


@app.get("/chat/complete/{task_id}")
async def get_response(task_id: str):
    if AsyncResult is None:
        raise HTTPException(status_code=503, detail="Celery result backend unavailable")

    start_time = time.time()
    while True:
        task_result = AsyncResult(task_id)
        task_status = task_result.status

        if task_status == "PENDING":
            if time.time() - start_time > TASK_TIMEOUT:
                return {
                    "task_id": task_id,
                    "task_status": task_result.status,
                    "task_result": task_result.result,
                    "error_message": "Service timeout, please retry",
                }
            time.sleep(POLLING_INTERVAL)
            continue

        return {
            "task_id": task_id,
            "task_status": task_result.status,
            "task_result": task_result.result,
        }


@app.post("/agent/answer")
async def agent_answer(data: AgentRequest):
    request_started = time.perf_counter()
    personalization_context = (
        safe_build_personalization_context(data.user_id) if data.user_id else {}
    )
    response = multi_agent_handle(
        data.question,
        history=data.history,
        user_id=data.user_id,
        user_profile=personalization_context,
    )
    return {
        "answer": response["content"],
        "status": response.get("status", "ok"),
        "fast_path": response.get("fast_path"),
        "latency_ms": round((time.perf_counter() - request_started) * 1000, 2),
        "agent_trace": response.get("agent_trace", []),
        "selected_agents": response.get("selected_agents", []),
        "tool_results": response.get("tool_results", []),
        "safety_result": response.get("safety_result", {}),
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
async def create_vector_collection(data: CollectionCreateRequest):
    try:
        from rag.qdrant.client import create_collection

        create_status = create_collection(data.collection_name, data.vector_size)
        return {"status": create_status is not None, "result": str(create_status)}
    except Exception as e:
        logger.error("Create collection failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document/create")
async def create_document(data: DocumentCreateRequest):
    try:
        index_status = index_document_v2(
            data.id,
            data.question,
            data.content,
            collection_name=data.collection_name,
            metadata=data.metadata,
        )
        initialize_search_index(
            [
                {
                    "doc_id": data.id,
                    "question": data.question,
                    "content": data.content,
                    "source": (data.metadata or {}).get("source", "api"),
                    "content_type": (data.metadata or {}).get("content_type"),
                    "domain": "health_inbody",
                }
            ]
        )
        return {"status": True, "index_status": index_status}
    except Exception as e:
        logger.error("Create/index document failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/index")
async def index_documents(data: DocumentsIndexRequest):
    try:
        result = index_health_documents(data.documents, collection_name=data.collection_name)
        return {"status": True, "result": result}
    except Exception as e:
        logger.error("Batch index failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
async def import_data_endpoint(data: DocumentsIndexRequest):
    result = index_health_documents(data.documents, collection_name=data.collection_name)
    return {"success": True, "result": result}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, workers=1, log_level="info")

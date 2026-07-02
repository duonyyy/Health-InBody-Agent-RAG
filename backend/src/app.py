"""FastAPI entrypoint cho Health/InBody Agent RAG backend."""
import logging
import time
from typing import Any, Dict, List, Optional

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import ai_agent_handle, get_agent_tools_summary
from cache import cache_health_check
from health_tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from search import get_search_stats, hybrid_search, initialize_search_index
from summarizer import summarize_health_report, summarize_text
from tasks import index_document_v2, index_health_documents, llm_handle_message
from utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

TASK_TIMEOUT = 60
POLLING_INTERVAL = 0.5
DEFAULT_COLLECTION_NAME = "nmk_chatbot_collection"

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
    user_id: str
    user_message: str
    history: Optional[List[Dict[str, str]]] = None
    sync_request: Optional[bool] = True


class AgentRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = None


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = True


class CollectionCreateRequest(BaseModel):
    collection_name: str = DEFAULT_COLLECTION_NAME
    vector_size: int = Field(default=1024, ge=1)


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
    weight_kg: float
    height_cm: float


class PbfRequest(BaseModel):
    pbf_percent: float
    sex: Optional[str] = None


class VisceralFatRequest(BaseModel):
    visceral_fat_level: float


class NutritionRequest(BaseModel):
    goal: str = "fat_loss"
    weight_kg: float
    activity_level: str = "moderate"


class TrainingRequest(BaseModel):
    goal: str = "fat_loss"
    fitness_level: str = "beginner"
    days_per_week: int = Field(default=3, ge=1, le=7)


class SafetyRequest(BaseModel):
    question: str
    conditions: Optional[List[str]] = None


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
        "agent": get_agent_tools_summary(),
    }


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
            if data.history:
                response = ai_agent_handle(data.user_message, history=data.history)
                return {"response": {"role": "assistant", "content": response}}
            response = llm_handle_message(data.bot_id, data.user_id, data.user_message)
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
    return {
        "answer": ai_agent_handle(data.question, history=data.history),
        "agent": get_agent_tools_summary(),
    }


@app.get("/agent/tools")
async def agent_tools():
    return get_agent_tools_summary()


@app.post("/search")
async def search_endpoint(data: SearchRequest):
    return {
        "query": data.query,
        "results": hybrid_search(data.query, limit=data.limit, use_rerank=data.use_rerank),
    }


@app.post("/collection/create")
async def create_vector_collection(data: CollectionCreateRequest):
    try:
        from vectorize import create_collection

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

    uvicorn.run("app:app", host="0.0.0.0", port=8000, workers=1, log_level="info")

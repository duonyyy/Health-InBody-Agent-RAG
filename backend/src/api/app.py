"""FastAPI entrypoint cho Health/InBody Agent RAG backend."""

import logging
import os
import time
from typing import Optional

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text as sql_text

from agents import get_multi_agent_summary
from api.auth import router as auth_router
from api.chat import (
    agent_answer,
    agent_tools,
    complete,
    get_response,
    router as chat_router,
)
from api.common import (
    DEFAULT_INDEX_MAX_BATCH_CHARS,
    DEFAULT_INDEX_MAX_BATCH_DOCS,
    DEFAULT_SEARCH_MAX_QUERY_CHARS,
    DEFAULT_SUMMARIZE_MAX_TEXT_CHARS,
    POLLING_INTERVAL,
    TASK_TIMEOUT,
    _allow_public_expensive_endpoints,
    _celery_queue_expires_seconds,
    _chat_timeout_seconds,
    _check_rate_limit_async,
    _env_float,
    _env_int,
    _health_probe_timeout_seconds,
    _indexing_timeout_seconds,
    _raise_lane_http_error,
    _resolve_expensive_caller,
    _search_timeout_seconds,
    _summarize_timeout_seconds,
    _task_poll_timeout_seconds,
    get_app_dep,
)
from api.corpus import (
    create_document,
    create_vector_collection,
    import_data_endpoint,
    index_documents,
    router as corpus_router,
)
from api.health_tools import (
    bmi_endpoint,
    nutrition_endpoint,
    pbf_endpoint,
    router as health_tools_router,
    safety_endpoint,
    training_endpoint,
    visceral_fat_endpoint,
)
from api.inbody_ocr import router as inbody_ocr_router
from api.memory import router as memory_router
from api.personalization import router as personalization_router
from api.schemas import (
    AgentRequest,
    BmiRequest,
    CollectionCreateRequest,
    CompleteRequest,
    DocumentCreateRequest,
    DocumentsIndexRequest,
    HistoryTurn,
    InBodyMeasurementRequest,
    NutritionRequest,
    PbfRequest,
    SafetyRequest,
    SearchRequest,
    SummaryRequest,
    TrainingRequest,
    UserProfileRequest,
    VisceralFatRequest,
)
from api.search import (
    router as search_router,
    search_endpoint,
    summarize_endpoint,
)
from api.users import (
    create_user_measurement,
    router as users_router,
    update_user_profile,
    user_measurements,
    user_personalization_context,
    user_profile,
)
from core.cache import cache_health_check, get_redis_client
from core.execution import CapacityExceededError, QueueTimeoutError, get_lane
from core.rate_limit import enforce_rate_limit
from core.utils import setup_logging
from harness.budget import (
    BudgetExhaustedError,
    RequestBudget,
    remaining_for_call,
)
from health.validation import InvalidHealthInput
from jobs.tasks import index_document_v2, index_health_documents, llm_handle_message
from llm.client import get_llm_runtime_config
from llm.summarizer import summarize_health_report, summarize_text
from memory import store as memory_store
from memory.chat import run_chat
from persistence.database import engine as database_engine
from rag.search import (
    get_search_stats,
    hybrid_search,
    load_search_snapshot,
    validate_lexical_worker_config,
    verify_runtime_release_sync,
)

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Health/InBody Agent RAG Backend",
    version="1.0.0-beta",
    description=(
        "Backend API cho chatbot Health/InBody RAG: chat, health tools, "
        "hybrid search, indexing và summarization."
    ),
)

_cors_origins = [value.strip() for value in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if value.strip()]
if os.getenv("AUTH_MODE", "production").strip().lower() == "development" and not _cors_origins:
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Dev-User-Id"],
)

# Mount all domain sub-routers
app.include_router(personalization_router)
app.include_router(auth_router)
if os.getenv("FEATURE_OCR_UPLOAD", "false").strip().lower() in {"1", "true", "yes", "on"}:
    app.include_router(inbody_ocr_router)
app.include_router(memory_router)
app.include_router(chat_router)
app.include_router(health_tools_router)
app.include_router(search_router)
app.include_router(corpus_router)
app.include_router(users_router)


@app.exception_handler(InvalidHealthInput)
async def invalid_health_input_handler(request: Request, exc: InvalidHealthInput) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_health_input"})


@app.on_event("startup")
def load_bm25_snapshot_on_startup():
    """Validate single-worker lexical ownership and load the versioned BM25 snapshot."""
    validate_lexical_worker_config()
    if os.getenv("BM25_AUTOLOAD", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info("BM25 snapshot autoload is disabled")
        return
    if not load_search_snapshot():
        logger.warning("BM25 snapshot unavailable or invalid; see /health/ready for corpus_release_sync")


@app.get("/")
async def root():
    return {
        "service": "Health/InBody Agent RAG Backend",
        "status": "ok",
        "docs": "/docs",
    }


def _health_report() -> dict:
    return {
        "status": "healthy",
        "service": "Health/InBody Agent RAG Backend",
        "cache": cache_health_check(),
        "search": get_search_stats(),
        "llm": get_llm_runtime_config(),
        "agent": get_multi_agent_summary(),
    }


@app.get("/health")
async def health():
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            _health_report,
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError):
        return {
            "status": "healthy",
            "service": "Health/InBody Agent RAG Backend",
            "cache": {"backend": "probe_skipped"},
            "search": get_search_stats(),
            "llm": get_llm_runtime_config(),
            "agent": get_multi_agent_summary(),
        }


def _readiness_report(deadline_monotonic: Optional[float] = None) -> dict:
    """Probe core dependencies without returning credentials or health records."""
    import requests

    effective_deadline = (
        time.monotonic() + _health_probe_timeout_seconds()
        if deadline_monotonic is None
        else float(deadline_monotonic)
    )
    dependencies = {"postgres": False, "qdrant": False, "valkey": False, "embedding_api": None}
    try:
        if remaining_for_call(effective_deadline, 2.0) is not None:
            with database_engine.connect() as connection:
                connection.execute(sql_text("SELECT 1"))
            dependencies["postgres"] = True
    except Exception as exc:
        logger.warning("Readiness PostgreSQL probe failed (%s)", type(exc).__name__)
    try:
        if remaining_for_call(effective_deadline, 1.5) is not None:
            redis_client = get_redis_client()
            dependencies["valkey"] = bool(redis_client and redis_client.ping())
    except Exception as exc:
        logger.warning("Readiness Valkey probe failed (%s)", type(exc).__name__)
    with requests.Session() as session:
        session.trust_env = False
        probes = [("qdrant", os.getenv("QDRANT_URL", "http://qdrant-db:6333").rstrip("/") + "/healthz")]
        if os.getenv("CUSTOM_EMBEDDING_ENABLED", "true").lower() == "true":
            probes.append(("embedding_api", os.getenv("CUSTOM_EMBEDDING_API_URL", "http://embedding-api:5000").rstrip("/") + "/health"))
        for name, url in probes:
            probe_timeout = remaining_for_call(effective_deadline, 2.0, min_timeout=0.1)
            if probe_timeout is None:
                dependencies[name] = False
                continue
            try:
                dependencies[name] = session.get(url, timeout=probe_timeout).status_code == 200
            except requests.RequestException as exc:
                logger.warning("Readiness %s probe failed (%s)", name, type(exc).__name__)
                dependencies[name] = False
    search_stats = get_search_stats()
    corpus_release_sync: Optional[bool] = None
    if search_stats.get("snapshot_error") or search_stats.get("release_sync_status") == "mismatch":
        corpus_release_sync = False
    elif dependencies.get("qdrant") and search_stats.get("initialized") and search_stats.get("physical_collection"):
        sync_info = verify_runtime_release_sync()
        corpus_release_sync = bool(sync_info.get("synced"))
    dependencies["corpus_release_sync"] = corpus_release_sync
    ready = all(value is not False for value in dependencies.values())
    return {
        "status": "ready" if ready else "degraded",
        "dependencies": dependencies,
        "corpus_release": {
            "release_id": search_stats.get("release_id"),
            "corpus_version": search_stats.get("corpus_version"),
            "physical_collection": search_stats.get("physical_collection"),
            "release_sync_status": search_stats.get("release_sync_status"),
            "release_mismatch_reason": search_stats.get("release_mismatch_reason"),
            "lexical_index_owner": search_stats.get("lexical_index_owner"),
        },
        "llm_provider": "not_checked",
    }


@app.get("/health/ready")
async def readiness():
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    report_fn = get_app_dep("_readiness_report", _readiness_report)
    try:
        result = await get_lane("probe").run(
            report_fn,
            deadline_monotonic=budget.deadline_monotonic,
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError):
        result = {
            "status": "degraded",
            "dependencies": {"postgres": False, "qdrant": False, "valkey": False, "embedding_api": None},
            "llm_provider": "not_checked",
        }
    return JSONResponse(result, status_code=200 if result["status"] == "ready" else 503)


# Re-exports for backwards compatibility with tests and callers
__all__ = [
    "app",
    "HistoryTurn",
    "CompleteRequest",
    "AgentRequest",
    "SearchRequest",
    "CollectionCreateRequest",
    "DocumentCreateRequest",
    "DocumentsIndexRequest",
    "SummaryRequest",
    "BmiRequest",
    "PbfRequest",
    "VisceralFatRequest",
    "NutritionRequest",
    "TrainingRequest",
    "SafetyRequest",
    "UserProfileRequest",
    "InBodyMeasurementRequest",
    "root",
    "health",
    "readiness",
    "complete",
    "get_response",
    "agent_answer",
    "agent_tools",
    "search_endpoint",
    "summarize_endpoint",
    "create_vector_collection",
    "create_document",
    "index_documents",
    "import_data_endpoint",
    "bmi_endpoint",
    "pbf_endpoint",
    "visceral_fat_endpoint",
    "nutrition_endpoint",
    "training_endpoint",
    "safety_endpoint",
    "user_profile",
    "update_user_profile",
    "user_measurements",
    "create_user_measurement",
    "user_personalization_context",
    "TASK_TIMEOUT",
    "POLLING_INTERVAL",
    "DEFAULT_SEARCH_MAX_QUERY_CHARS",
    "DEFAULT_SUMMARIZE_MAX_TEXT_CHARS",
    "DEFAULT_INDEX_MAX_BATCH_DOCS",
    "DEFAULT_INDEX_MAX_BATCH_CHARS",
    "_env_float",
    "_env_int",
    "_chat_timeout_seconds",
    "_search_timeout_seconds",
    "_summarize_timeout_seconds",
    "_indexing_timeout_seconds",
    "_health_probe_timeout_seconds",
    "_task_poll_timeout_seconds",
    "_celery_queue_expires_seconds",
    "_allow_public_expensive_endpoints",
    "_resolve_expensive_caller",
    "_check_rate_limit_async",
    "_raise_lane_http_error",
    "run_chat",
    "memory_store",
    "llm_handle_message",
    "hybrid_search",
    "summarize_text",
    "summarize_health_report",
    "index_document_v2",
    "index_health_documents",
    "enforce_rate_limit",
    "AsyncResult",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, workers=1, log_level="info")

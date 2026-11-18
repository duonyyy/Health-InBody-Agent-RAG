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

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from starlette.concurrency import run_in_threadpool

from agents import get_multi_agent_summary, multi_agent_handle
from agents.constants import AGENT_MAX_REQUEST_TIMEOUT_SECONDS, AGENT_REQUEST_TIMEOUT_SECONDS
from llm.client import get_llm_runtime_config
from core.cache import cache_health_check
from core.cache import get_redis_client
from core.config import DEFAULT_COLLECTION_NAME, DEFAULT_VECTOR_SIZE
from core.execution import (
    CapacityExceededError,
    QueueTimeoutError,
    get_lane,
)
from core.rate_limit import (
    RateLimiterUnavailableError,
    RateLimitExceededError,
    enforce_rate_limit,
)
from harness.budget import (
    BudgetExhaustedError,
    RequestBudget,
    call_with_supported_kwargs,
    remaining_for_call,
)
from health.tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from health.validation import InvalidHealthInput, validate_health_input
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
from api.auth import router as auth_router
from api.inbody_ocr import router as inbody_ocr_router
from api.personalization import _execute
from api.memory import router as memory_router
from memory.chat import run_chat
from memory import store as memory_store
from auth.context import (
    CurrentUser,
    auth_mode,
    get_current_user,
    get_optional_current_user,
    require_corpus_admin,
    require_legacy_user_match,
)
from rag.corpus_policy import validate_shared_document, require_staging_collection
from persistence.personalization_service import (
    redacted_context,
    safe_build_confirmed_context,
)
from persistence.database import engine as database_engine

setup_logging()
logger = logging.getLogger(__name__)

TASK_TIMEOUT = 50
POLLING_INTERVAL = 0.5
DEFAULT_SEARCH_MAX_QUERY_CHARS = 500
DEFAULT_SUMMARIZE_MAX_TEXT_CHARS = 12000
DEFAULT_INDEX_MAX_BATCH_DOCS = 50
DEFAULT_INDEX_MAX_BATCH_CHARS = 250000


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, min(maximum, default))
    try:
        return max(minimum, min(maximum, float(raw)))
    except ValueError:
        return max(minimum, min(maximum, default))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, min(maximum, default))
    try:
        return max(minimum, min(maximum, int(raw)))
    except ValueError:
        return max(minimum, min(maximum, default))


def _chat_timeout_seconds() -> float:
    return _env_float(
        "AGENT_REQUEST_TIMEOUT_SECONDS",
        AGENT_REQUEST_TIMEOUT_SECONDS,
        minimum=0.2,
        maximum=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
    )


def _search_timeout_seconds() -> float:
    return _env_float("SEARCH_TIMEOUT_SECONDS", 15.0, minimum=0.1, maximum=30.0)


def _summarize_timeout_seconds() -> float:
    return _env_float("SUMMARIZE_TIMEOUT_SECONDS", 25.0, minimum=0.1, maximum=45.0)


def _indexing_timeout_seconds() -> float:
    return _env_float("INDEXING_TIMEOUT_SECONDS", 45.0, minimum=0.5, maximum=55.0)


def _health_probe_timeout_seconds() -> float:
    return _env_float("HEALTH_PROBE_TIMEOUT_SECONDS", 5.0, minimum=0.2, maximum=10.0)


def _task_poll_timeout_seconds() -> float:
    return _env_float("TASK_TIMEOUT_SECONDS", float(TASK_TIMEOUT), minimum=0.5, maximum=55.0)


def _celery_queue_expires_seconds() -> int:
    return _env_int("CELERY_QUEUE_EXPIRES_SECONDS", 55, minimum=5, maximum=60)


def _allow_public_expensive_endpoints() -> bool:
    return os.getenv("ALLOW_PUBLIC_EXPENSIVE_ENDPOINTS", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _resolve_expensive_caller(request: Request) -> tuple:
    user = get_optional_current_user(request)
    if user is None and auth_mode() == "production" and not _allow_public_expensive_endpoints():
        raise HTTPException(
            status_code=401,
            detail="Authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    peer = request.client.host if request.client else "unknown"
    if user is not None:
        return user, f"user:{user.subject}"
    return None, f"ip:{peer}"


async def _check_rate_limit_async(bucket: str, identifier: str, limit: int, budget: RequestBudget) -> None:
    limiter_budget = RequestBudget.from_deadline(
        min(budget.deadline_monotonic, time.monotonic() + 2.0),
    )
    try:
        await get_lane("probe").run(
            enforce_rate_limit,
            bucket=bucket,
            identifier=identifier,
            limit=limit,
            window_seconds=60,
            budget=limiter_budget,
            pass_cancel_event=False,
        )
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail="Bạn gửi yêu cầu quá nhanh. Vui lòng chờ và thử lại.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except RateLimiterUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Hệ thống kiểm soát lưu lượng tạm thời không khả dụng. Vui lòng thử lại sau.",
            headers={"Retry-After": "5"},
        ) from exc
    except (CapacityExceededError, QueueTimeoutError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Hệ thống đang bận xử lý nhiều yêu cầu. Vui lòng thử lại sau.",
            headers={"Retry-After": "2"},
        ) from exc
    except BudgetExhaustedError as exc:
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu quá thời gian xử lý cho phép. Vui lòng thử lại.",
        ) from exc


def _raise_lane_http_error(exc: Exception) -> None:
    if isinstance(exc, (CapacityExceededError, QueueTimeoutError)):
        raise HTTPException(
            status_code=503,
            detail="Hệ thống đang bận xử lý nhiều yêu cầu. Vui lòng thử lại sau.",
            headers={"Retry-After": "2"},
        ) from exc
    if isinstance(exc, BudgetExhaustedError):
        raise HTTPException(
            status_code=504,
            detail="Yêu cầu quá thời gian xử lý cho phép. Vui lòng thử lại.",
        ) from exc
    raise exc

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
    CORSMiddleware, allow_origins=_cors_origins, allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Dev-User-Id"],
)
app.include_router(personalization_router)
app.include_router(auth_router)
if os.getenv("FEATURE_OCR_UPLOAD", "false").strip().lower() in {"1", "true", "yes", "on"}:
    app.include_router(inbody_ocr_router)
app.include_router(memory_router)


@app.exception_handler(InvalidHealthInput)
async def invalid_health_input_handler(request: Request, exc: InvalidHealthInput) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_health_input"})


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
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = True


class CollectionCreateRequest(BaseModel):
    collection_name: str = DEFAULT_COLLECTION_NAME
    vector_size: int = Field(default=DEFAULT_VECTOR_SIZE, ge=1)


class DocumentCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    question: Optional[str] = Field(default="", max_length=2000)
    content: str = Field(min_length=1, max_length=100000)
    collection_name: str = DEFAULT_COLLECTION_NAME
    metadata: Optional[Dict[str, Any]] = None


class DocumentsIndexRequest(BaseModel):
    documents: List[Dict[str, Any]] = Field(min_length=1, max_length=100)
    collection_name: str = DEFAULT_COLLECTION_NAME


class SummaryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
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
    question: str = Field(min_length=1, max_length=4000)
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
    ready = all(value is not False for value in dependencies.values())
    return {"status": "ready" if ready else "degraded", "dependencies": dependencies,
            "llm_provider": "not_checked"}


@app.get("/health/ready")
async def readiness():
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        result = await get_lane("probe").run(
            _readiness_report,
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


@app.get("/users/{user_id}/profile")
async def user_profile(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            get_user_profile, user_id, auto_create=True, budget=budget, pass_cancel_event=False
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
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
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            upsert_user_profile,
            user_id,
            data.dict(exclude_unset=True),
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
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
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        items = await get_lane("probe").run(
            list_inbody_measurements, user_id, limit=limit, budget=budget, pass_cancel_event=False
        )
        return {"measurements": items}
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
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
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            add_inbody_measurement,
            user_id,
            data.dict(exclude_unset=True),
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Create user measurement failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to create user measurement")


@app.get("/users/{user_id}/personalization-context")
async def user_personalization_context(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            redacted_context, current_user.subject, budget=budget, pass_cancel_event=False
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)


def _run_chat_in_lane(
    question: str,
    subject: str,
    *,
    bot_id: str = "health-inbody-agent",
    use_zep_memory: bool = False,
    conversation_id=None,
    deadline_monotonic: Optional[float] = None,
    cancel_event: Any = None,
) -> dict:
    return _execute(
        call_with_supported_kwargs,
        run_chat,
        question,
        subject,
        bot_id=bot_id,
        use_zep_memory=use_zep_memory,
        conversation_id=conversation_id,
        deadline_monotonic=deadline_monotonic,
        cancel_event=cancel_event,
    )


def _poll_celery_task(task_id: str) -> tuple:
    task_result = AsyncResult(task_id)
    task_status = task_result.status
    if task_status == "SUCCESS":
        return task_status, task_result.result
    return task_status, None


@app.post("/chat/complete")
async def complete(data: CompleteRequest, current_user: CurrentUser = Depends(get_current_user)):
    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info(
        "Chat request received bot_id=%s sync=%s",
        data.bot_id,
        data.sync_request,
    )

    # Emergency requests must never wait for rate limits, expensive lanes, Celery, or storage.
    request_started = time.perf_counter()
    urgent = check_medical_safety(data.user_message).get("risk_level") == "urgent"
    if urgent:
        response = _execute(
            call_with_supported_kwargs,
            run_chat,
            data.user_message,
            current_user.subject,
            bot_id=data.bot_id,
            use_zep_memory=False,
            conversation_id=None,
        )
        response["latency_ms"] = round((time.perf_counter() - request_started) * 1000, 2)
        return {"response": response}

    validate_health_input(data.user_message)
    budget = RequestBudget.start(
        _chat_timeout_seconds(),
        max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
    )
    chat_limit = _env_int("CHAT_RATE_LIMIT_PER_MINUTE", 30, minimum=0, maximum=1000)
    await _check_rate_limit_async("chat", f"user:{current_user.subject}", chat_limit, budget)

    if data.sync_request:
        try:
            response = await get_lane("chat").run(
                _run_chat_in_lane,
                data.user_message,
                current_user.subject,
                bot_id=data.bot_id,
                use_zep_memory=_memory_identity_allowed(current_user),
                conversation_id=data.conversation_id,
                deadline_monotonic=budget.deadline_monotonic,
                budget=budget,
            )
            response["latency_ms"] = round(
                (time.perf_counter() - request_started) * 1000,
                2,
            )
            return {"response": response}
        except HTTPException:
            raise
        except InvalidHealthInput:
            raise
        except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
            _raise_lane_http_error(exc)
        except Exception as e:
            logger.error("Chat sync failed (%s)", type(e).__name__)
            raise HTTPException(status_code=500, detail="Không thể hoàn tất yêu cầu hội thoại.")

    if not hasattr(llm_handle_message, "apply_async"):
        raise HTTPException(
            status_code=503,
            detail="Hàng đợi hội thoại hiện không khả dụng; vui lòng dùng sync_request=true.",
        )

    try:
        if data.conversation_id:
            await get_lane("probe").run(
                _execute,
                memory_store.load_history,
                current_user.subject,
                str(data.conversation_id),
                budget=budget,
                pass_cancel_event=False,
            )
        task_id = await get_lane("probe").run(
            _execute,
            memory_store.create_task,
            current_user.subject,
            budget=budget,
            pass_cancel_event=False,
        )
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)

    queue_expires = _celery_queue_expires_seconds()
    deadline_epoch = time.time() + float(queue_expires)
    try:
        await get_lane("probe").run(
            llm_handle_message.apply_async,
            args=[
                data.bot_id,
                current_user.subject,
                data.user_message,
                str(data.conversation_id) if data.conversation_id else None,
            ],
            task_id=task_id,
            expires=queue_expires,
            kwargs={"task_id": task_id, "deadline_epoch": deadline_epoch},
            argsrepr="[redacted chat arguments]",
            kwargsrepr="{redacted task metadata}",
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.warning("Chat dispatch failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Hàng đợi hội thoại tạm thời không khả dụng") from exc
    return {"task_id": task_id}


@app.get("/chat/complete/{task_id}")
async def get_response(task_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    task_id = str(task_id)
    budget = RequestBudget.start(_task_poll_timeout_seconds(), max_timeout_seconds=55.0)
    try:
        await get_lane("probe").run(
            _execute,
            memory_store.require_task_owner,
            current_user.subject,
            task_id,
            budget=budget,
            pass_cancel_event=False,
        )
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)

    if AsyncResult is None:
        raise HTTPException(status_code=503, detail="Celery result backend unavailable")

    while True:
        if budget.exhausted():
            raise HTTPException(status_code=504, detail="Yêu cầu chờ kết quả quá thời gian cho phép. Vui lòng thử lại.")
        try:
            task_status, task_result_value = await get_lane("probe").run(
                _poll_celery_task,
                task_id,
                budget=budget,
                pass_cancel_event=False,
            )
        except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
            _raise_lane_http_error(exc)
        except Exception as exc:
            logger.warning("Celery result lookup failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Không thể kiểm tra trạng thái yêu cầu hội thoại.") from exc

        if task_status in {"PENDING", "STARTED", "RETRY"}:
            remaining = budget.remaining_seconds()
            if remaining <= 0.0:
                raise HTTPException(status_code=504, detail="Yêu cầu chờ kết quả quá thời gian cho phép. Vui lòng thử lại.")
            await asyncio.sleep(min(POLLING_INTERVAL, remaining))
            continue

        if task_status != "SUCCESS":
            raise HTTPException(status_code=502, detail="Không thể hoàn thành yêu cầu hội thoại")
        return {
            "task_id": task_id,
            "task_status": task_status,
            "task_result": task_result_value,
        }


@app.post("/agent/answer")
async def agent_answer(data: AgentRequest, current_user: CurrentUser = Depends(get_current_user)):
    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    request_started = time.perf_counter()
    # Deterministic urgent pre-check runs BEFORE rate limits, expensive lanes, DB, or LLM/RAG.
    urgent = check_medical_safety(data.question).get("risk_level") == "urgent"
    if urgent:
        response = _execute(
            call_with_supported_kwargs,
            run_chat,
            data.question,
            current_user.subject,
            use_zep_memory=False,
            conversation_id=None,
        )
    else:
        validate_health_input(data.question)
        budget = RequestBudget.start(
            _chat_timeout_seconds(),
            max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
        )
        chat_limit = _env_int("CHAT_RATE_LIMIT_PER_MINUTE", 30, minimum=0, maximum=1000)
        await _check_rate_limit_async("chat", f"user:{current_user.subject}", chat_limit, budget)
        try:
            response = await get_lane("chat").run(
                _run_chat_in_lane,
                data.question,
                current_user.subject,
                use_zep_memory=_memory_identity_allowed(current_user),
                conversation_id=data.conversation_id,
                deadline_monotonic=budget.deadline_monotonic,
                budget=budget,
            )
        except HTTPException:
            raise
        except InvalidHealthInput:
            raise
        except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
            _raise_lane_http_error(exc)

    return {
        "answer": response["content"],
        "request_id": response.get("request_id"),
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
async def search_endpoint(data: SearchRequest, request: Request):
    query = data.query.strip()
    max_query_chars = _env_int("SEARCH_MAX_QUERY_CHARS", DEFAULT_SEARCH_MAX_QUERY_CHARS, minimum=1, maximum=2000)
    if not query or len(query) > max_query_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Truy vấn tìm kiếm không hợp lệ (tối đa {max_query_chars} ký tự).",
        )
    user, caller_id = _resolve_expensive_caller(request)
    budget = RequestBudget.start(_search_timeout_seconds(), max_timeout_seconds=30.0)
    default_limit = 30 if user is not None else 60
    rate_limit = _env_int("SEARCH_RATE_LIMIT_PER_MINUTE", default_limit, minimum=0, maximum=1000)
    await _check_rate_limit_async("search", caller_id, rate_limit, budget)
    try:
        results = await get_lane("search").run(
            hybrid_search,
            query,
            limit=data.limit,
            use_rerank=data.use_rerank,
            timeout=budget.remaining_seconds(),
            deadline_monotonic=budget.deadline_monotonic,
            raise_on_timeout=True,
            budget=budget,
            pass_cancel_event=False,
        )
        return {
            "query": query,
            "results": results,
        }
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.warning("Search endpoint failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ tìm kiếm tạm thời không khả dụng. Vui lòng thử lại sau.",
        ) from exc


@app.post("/collection/create")
async def create_vector_collection(data: CollectionCreateRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_corpus_admission(data.collection_name, [])
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    await _check_rate_limit_async("indexing", f"admin:{admin.subject}", index_limit, budget)
    try:
        from rag.qdrant.client import create_collection

        create_status = await get_lane("indexing").run(
            create_collection,
            data.collection_name,
            data.vector_size,
            budget=budget,
            pass_cancel_event=False,
        )
        return {"status": create_status is not None, "result": str(create_status)}
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Create collection failed (%s)", type(e).__name__)
        raise HTTPException(status_code=503, detail="Không thể tạo collection lúc này.")


@app.post("/document/create")
async def create_document(data: DocumentCreateRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_corpus_admission(data.collection_name, [data.model_dump()])
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    await _check_rate_limit_async("indexing", f"admin:{admin.subject}", index_limit, budget)
    try:
        index_status = await get_lane("indexing").run(
            index_document_v2,
            data.id,
            data.question,
            data.content,
            collection_name=data.collection_name,
            metadata=data.metadata,
            budget=budget,
            pass_cancel_event=False,
        )
        return {"status": True, "index_status": index_status}
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Create/index document failed (%s)", type(e).__name__)
        raise HTTPException(status_code=503, detail="Không thể lập chỉ mục tài liệu lúc này.")


@app.post("/documents/index")
async def index_documents(data: DocumentsIndexRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_index_batch_limits(data.documents)
    _validate_corpus_admission(data.collection_name, data.documents)
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    await _check_rate_limit_async("indexing", f"admin:{admin.subject}", index_limit, budget)
    try:
        result = await get_lane("indexing").run(
            index_health_documents,
            data.documents,
            collection_name=data.collection_name,
            budget=budget,
            pass_cancel_event=False,
        )
        return {"status": True, "result": result}
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Batch index failed (%s)", type(e).__name__)
        raise HTTPException(status_code=503, detail="Không thể lập chỉ mục lô tài liệu lúc này.")


@app.post("/summarize")
async def summarize_endpoint(data: SummaryRequest, request: Request):
    text = data.text.strip()
    max_text_chars = _env_int(
        "SUMMARIZE_MAX_TEXT_CHARS",
        DEFAULT_SUMMARIZE_MAX_TEXT_CHARS,
        minimum=1,
        maximum=50000,
    )
    if not text or len(text) > max_text_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Nội dung cần tóm tắt không hợp lệ (tối đa {max_text_chars} ký tự).",
        )
    user, caller_id = _resolve_expensive_caller(request)
    budget = RequestBudget.start(_summarize_timeout_seconds(), max_timeout_seconds=45.0)
    default_limit = 10 if user is not None else 20
    rate_limit = _env_int("SUMMARIZE_RATE_LIMIT_PER_MINUTE", default_limit, minimum=0, maximum=1000)
    await _check_rate_limit_async("summarize", caller_id, rate_limit, budget)
    target_fn = summarize_health_report if data.report_mode else summarize_text
    try:
        summary = await get_lane("summarize").run(
            target_fn,
            text,
            timeout=budget.remaining_seconds(),
            deadline_monotonic=budget.deadline_monotonic,
            raise_on_timeout=True,
            budget=budget,
            pass_cancel_event=False,
        )
        return {"summary": summary}
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.warning("Summarize endpoint failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ tóm tắt tạm thời không khả dụng. Vui lòng thử lại sau.",
        ) from exc


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
    _validate_index_batch_limits(data.documents)
    _validate_corpus_admission(data.collection_name, data.documents)
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    await _check_rate_limit_async("indexing", f"admin:{admin.subject}", index_limit, budget)
    try:
        result = await get_lane("indexing").run(
            index_health_documents,
            data.documents,
            collection_name=data.collection_name,
            budget=budget,
            pass_cancel_event=False,
        )
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.error("Data import failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không thể nhập dữ liệu lúc này.") from exc


def _validate_index_batch_limits(documents: list) -> None:
    max_docs = _env_int("INDEX_MAX_BATCH_DOCS", DEFAULT_INDEX_MAX_BATCH_DOCS, minimum=1, maximum=100)
    if len(documents) > max_docs:
        raise HTTPException(
            status_code=422,
            detail=f"Số tài liệu trong một lô vượt quá giới hạn ({max_docs}).",
        )
    max_chars = _env_int("INDEX_MAX_BATCH_CHARS", DEFAULT_INDEX_MAX_BATCH_CHARS, minimum=1000, maximum=2000000)
    total_chars = sum(
        len(str(doc.get("content") or doc.get("page_content") or ""))
        + len(str(doc.get("question") or doc.get("title") or ""))
        for doc in documents
        if isinstance(doc, dict)
    )
    if total_chars > max_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Tổng dung lượng văn bản trong lô vượt quá giới hạn ({max_chars} ký tự).",
        )


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

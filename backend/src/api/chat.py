"""Chat and agent orchestration endpoints."""

import logging
import time
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Depends as DependsClass
from fastapi.responses import JSONResponse

from agents import get_multi_agent_summary
from agents.constants import AGENT_MAX_REQUEST_TIMEOUT_SECONDS
from api.common import (
    _celery_queue_expires_seconds,
    _chat_timeout_seconds,
    _env_float,
    _env_int,
    _raise_lane_http_error,
)
from api.dependencies import (
    get_chat_service,
    get_rate_limit_checker,
)
from api.schemas import AgentRequest, CompleteRequest
from auth.context import CurrentUser, get_current_user
from core.execution import CapacityExceededError, QueueTimeoutError
from harness.budget import BudgetExhaustedError, RequestBudget
from health.tools import check_medical_safety
from health.validation import InvalidHealthInput, validate_health_input
from services.chat_service import (
    CeleryBackendUnavailableError,
    ChatService,
    QueueUnavailableError,
    TaskExecutionFailedError,
    _poll_celery_task_lane as _poll_celery_task,
    _run_chat_in_lane,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _resolve_dep(val: Any, default_getter: Any) -> Any:
    if isinstance(val, DependsClass):
        return default_getter()
    return val


@router.post("/chat/complete")
async def complete(
    data: CompleteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: Any = Depends(get_chat_service),
    check_rate_limit: Any = Depends(get_rate_limit_checker),
):
    chat_service = _resolve_dep(chat_service, get_chat_service)
    check_rate_limit = _resolve_dep(check_rate_limit, get_rate_limit_checker)

    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info(
        "Chat request received bot_id=%s sync=%s",
        data.bot_id,
        data.sync_request,
    )

    request_started = time.perf_counter()
    urgent = check_medical_safety(data.user_message).get("risk_level") == "urgent"
    if urgent:
        response = await chat_service.execute_sync_chat(
            data.user_message,
            current_user.subject,
            bot_id=data.bot_id,
            conversation_id=None,
            urgent=True,
        )
        response["latency_ms"] = round((time.perf_counter() - request_started) * 1000, 2)
        return {"response": response}

    validate_health_input(data.user_message)
    budget = RequestBudget.start(
        _chat_timeout_seconds(),
        max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
    )
    chat_limit = _env_int("CHAT_RATE_LIMIT_PER_MINUTE", 30, minimum=0, maximum=1000)
    await check_rate_limit("chat", f"user:{current_user.subject}", chat_limit, budget)

    if data.sync_request:
        try:
            response = await chat_service.execute_sync_chat(
                data.user_message,
                current_user.subject,
                bot_id=data.bot_id,
                conversation_id=data.conversation_id,
                budget=budget,
                urgent=False,
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

    try:
        task_id = await chat_service.dispatch_async_chat(
            data.user_message,
            current_user.subject,
            bot_id=data.bot_id,
            conversation_id=data.conversation_id,
            budget=budget,
            queue_expires=_celery_queue_expires_seconds(),
        )
        return {"task_id": task_id}
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.warning("Chat dispatch failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Hàng đợi hội thoại tạm thời không khả dụng") from exc


@router.get("/chat/complete/{task_id}")
async def get_response(
    task_id: UUID,
    wait: bool = Query(default=True, description="Chờ kết quả trong khoảng thời gian ngắn hoặc trả về ngay trạng thái hiện tại"),
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: Any = Depends(get_chat_service),
):
    chat_service = _resolve_dep(chat_service, get_chat_service)
    task_id_str = str(task_id)

    hold_limit = _env_float("TASK_POLL_HOLD_SECONDS", 10.0, minimum=0.5, maximum=20.0) if wait else 0.0
    budget = RequestBudget.start(hold_limit, max_timeout_seconds=20.0) if wait else RequestBudget.start(2.0, max_timeout_seconds=5.0)

    try:
        poll_result = await chat_service.poll_task_status(
            task_id_str,
            current_user.subject,
            wait=wait,
            hold_limit=hold_limit,
            budget=budget,
        )
    except HTTPException:
        raise
    except CeleryBackendUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TaskExecutionFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.warning("Celery result lookup failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không thể kiểm tra trạng thái yêu cầu hội thoại.") from exc

    if not poll_result.is_ready:
        return JSONResponse(
            status_code=200,
            content={
                "task_id": poll_result.task_id,
                "task_status": poll_result.status,
                "task_result": None,
            },
            headers={"Retry-After": poll_result.retry_after or "1"},
        )

    return {
        "task_id": poll_result.task_id,
        "task_status": poll_result.status,
        "task_result": poll_result.result,
    }


@router.post("/agent/answer")
async def agent_answer(
    data: AgentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: Any = Depends(get_chat_service),
    check_rate_limit: Any = Depends(get_rate_limit_checker),
):
    chat_service = _resolve_dep(chat_service, get_chat_service)
    check_rate_limit = _resolve_dep(check_rate_limit, get_rate_limit_checker)

    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    request_started = time.perf_counter()
    urgent = check_medical_safety(data.question).get("risk_level") == "urgent"
    if not urgent:
        validate_health_input(data.question)
        budget = RequestBudget.start(
            _chat_timeout_seconds(),
            max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
        )
        chat_limit = _env_int("CHAT_RATE_LIMIT_PER_MINUTE", 30, minimum=0, maximum=1000)
        await check_rate_limit("chat", f"user:{current_user.subject}", chat_limit, budget)
    else:
        budget = None

    try:
        return await chat_service.execute_agent_answer(
            data.question,
            current_user.subject,
            conversation_id=data.conversation_id,
            budget=budget,
            request_started=request_started,
            urgent=urgent,
        )
    except HTTPException:
        raise
    except InvalidHealthInput:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)


@router.get("/agent/tools")
async def agent_tools():
    return get_multi_agent_summary()

"""Chat and agent orchestration endpoints."""

import asyncio
import logging
import time
from typing import Any, Optional
from uuid import UUID

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from agents import get_multi_agent_summary
from agents.constants import AGENT_MAX_REQUEST_TIMEOUT_SECONDS
from api.common import (
    POLLING_INTERVAL,
    _celery_queue_expires_seconds,
    _chat_timeout_seconds,
    _check_rate_limit_async,
    _env_float,
    _env_int,
    _raise_lane_http_error,
    get_app_dep,
)
from api.personalization import _execute
from api.schemas import AgentRequest, CompleteRequest
from auth.context import CurrentUser, get_current_user
from core.execution import CapacityExceededError, QueueTimeoutError, get_lane
from harness.budget import BudgetExhaustedError, RequestBudget, call_with_supported_kwargs
from health.tools import check_medical_safety
from health.validation import InvalidHealthInput, validate_health_input
from jobs.tasks import llm_handle_message
from memory import store as memory_store
from memory.chat import run_chat

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _run_chat_in_lane(
    question: str,
    subject: str,
    *,
    bot_id: str = "health-inbody-agent",
    conversation_id=None,
    deadline_monotonic: Optional[float] = None,
    cancel_event: Any = None,
) -> dict:
    chat_fn = get_app_dep("run_chat", run_chat)
    return _execute(
        call_with_supported_kwargs,
        chat_fn,
        question,
        subject,
        bot_id=bot_id,
        conversation_id=conversation_id,
        deadline_monotonic=deadline_monotonic,
        cancel_event=cancel_event,
    )


def _poll_celery_task(task_id: str) -> tuple:
    async_result_cls = get_app_dep("AsyncResult", AsyncResult)
    task_result = async_result_cls(task_id)
    task_status = task_result.status
    if task_status == "SUCCESS":
        return task_status, task_result.result
    return task_status, None


@router.post("/chat/complete")
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
        chat_fn = get_app_dep("run_chat", run_chat)
        response = _execute(
            call_with_supported_kwargs,
            chat_fn,
            data.user_message,
            current_user.subject,
            bot_id=data.bot_id,
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
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("chat", f"user:{current_user.subject}", chat_limit, budget)

    if data.sync_request:
        try:
            response = await get_lane("chat").run(
                _run_chat_in_lane,
                data.user_message,
                current_user.subject,
                bot_id=data.bot_id,
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

    llm_handler = get_app_dep("llm_handle_message", llm_handle_message)
    if not hasattr(llm_handler, "apply_async"):
        raise HTTPException(
            status_code=503,
            detail="Hàng đợi hội thoại hiện không khả dụng; vui lòng dùng sync_request=true.",
        )

    store = get_app_dep("memory_store", memory_store)
    try:
        if data.conversation_id:
            await get_lane("probe").run(
                _execute,
                store.load_history,
                current_user.subject,
                str(data.conversation_id),
                budget=budget,
                pass_cancel_event=False,
            )
        task_id = await get_lane("probe").run(
            _execute,
            store.create_task,
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
            llm_handler.apply_async,
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


@router.get("/chat/complete/{task_id}")
async def get_response(
    task_id: UUID,
    wait: bool = Query(default=True, description="Chờ kết quả trong khoảng thời gian ngắn hoặc trả về ngay trạng thái hiện tại"),
    current_user: CurrentUser = Depends(get_current_user),
):
    task_id = str(task_id)
    # Giới hạn thời gian giữ kết nối (mặc định tối đa 10s) để tránh treo HTTP connection và bão hòa lane probe
    hold_limit = _env_float("TASK_POLL_HOLD_SECONDS", 10.0, minimum=0.5, maximum=20.0) if wait else 0.0
    budget = RequestBudget.start(hold_limit, max_timeout_seconds=20.0) if wait else RequestBudget.start(2.0, max_timeout_seconds=5.0)
    store = get_app_dep("memory_store", memory_store)
    try:
        await get_lane("probe").run(
            _execute,
            store.require_task_owner,
            current_user.subject,
            task_id,
            budget=budget,
            pass_cancel_event=False,
        )
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)

    async_result_cls = get_app_dep("AsyncResult", AsyncResult)
    if async_result_cls is None:
        raise HTTPException(status_code=503, detail="Celery result backend unavailable")

    while True:
        try:
            task_status, task_result_value = await get_lane("probe").run(
                _poll_celery_task,
                task_id,
                budget=budget,
                pass_cancel_event=False,
            )
        except BudgetExhaustedError:
            return JSONResponse(
                status_code=200,
                content={
                    "task_id": task_id,
                    "task_status": "STARTED",
                    "task_result": None,
                },
                headers={"Retry-After": "1"},
            )
        except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
            _raise_lane_http_error(exc)
        except Exception as exc:
            logger.warning("Celery result lookup failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Không thể kiểm tra trạng thái yêu cầu hội thoại.") from exc

        if task_status in {"PENDING", "STARTED", "RETRY"}:
            if not wait or budget.exhausted():
                return JSONResponse(
                    status_code=200,
                    content={
                        "task_id": task_id,
                        "task_status": task_status,
                        "task_result": None,
                    },
                    headers={"Retry-After": "1"},
                )
            remaining = budget.remaining_seconds()
            if remaining <= 0.0:
                return JSONResponse(
                    status_code=200,
                    content={
                        "task_id": task_id,
                        "task_status": task_status,
                        "task_result": None,
                    },
                    headers={"Retry-After": "1"},
                )
            await asyncio.sleep(min(POLLING_INTERVAL, remaining))
            continue

        if task_status != "SUCCESS":
            raise HTTPException(status_code=502, detail="Không thể hoàn thành yêu cầu hội thoại")
        return {
            "task_id": task_id,
            "task_status": task_status,
            "task_result": task_result_value,
        }


@router.post("/agent/answer")
async def agent_answer(data: AgentRequest, current_user: CurrentUser = Depends(get_current_user)):
    if data.user_id is not None and data.user_id != current_user.subject:
        raise HTTPException(status_code=403, detail="Forbidden")

    request_started = time.perf_counter()
    # Deterministic urgent pre-check runs BEFORE rate limits, expensive lanes, DB, or LLM/RAG.
    urgent = check_medical_safety(data.question).get("risk_level") == "urgent"
    if urgent:
        chat_fn = get_app_dep("run_chat", run_chat)
        response = _execute(
            call_with_supported_kwargs,
            chat_fn,
            data.question,
            current_user.subject,
            conversation_id=None,
        )
    else:
        validate_health_input(data.question)
        budget = RequestBudget.start(
            _chat_timeout_seconds(),
            max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
        )
        chat_limit = _env_int("CHAT_RATE_LIMIT_PER_MINUTE", 30, minimum=0, maximum=1000)
        check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
        await check_rate_limit("chat", f"user:{current_user.subject}", chat_limit, budget)
        try:
            response = await get_lane("chat").run(
                _run_chat_in_lane,
                data.question,
                current_user.subject,
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
        "retrieval_status": response.get("retrieval_status"),
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


@router.get("/agent/tools")
async def agent_tools():
    return get_multi_agent_summary()

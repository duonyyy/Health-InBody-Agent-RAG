"""Chat orchestration service layer for Health/InBody Agent RAG.

Separates orchestration, Celery task scheduling, polling loops, and execution lanes
from HTTP presentation boundary according to python-common-patterns (references/service-layer.md).
"""

import asyncio
from dataclasses import dataclass
import logging
import time
from typing import Any, Callable, Dict, Optional

from agents import get_multi_agent_summary
from api.personalization import _execute
from core.execution import CapacityExceededError, QueueTimeoutError, get_lane
from harness.budget import (
    BudgetExhaustedError,
    RequestBudget,
    call_with_supported_kwargs,
)

logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Base domain exception for chat service failures."""


class QueueUnavailableError(ChatServiceError):
    """Raised when the Celery async task queue is unavailable."""


class TaskNotFoundError(ChatServiceError):
    """Raised when a chat task does not exist or owner mismatch occurs."""


class TaskExecutionFailedError(ChatServiceError):
    """Raised when a Celery background worker failed to complete the chat request."""


class CeleryBackendUnavailableError(ChatServiceError):
    """Raised when Celery result backend is unavailable for polling."""


@dataclass(frozen=True)
class ChatPollResult:
    """Outcome of polling an asynchronous chat task."""
    task_id: str
    status: str
    result: Optional[Any] = None
    retry_after: Optional[str] = None
    is_ready: bool = False


def _run_chat_in_lane(
    question: str,
    subject: str,
    *,
    bot_id: str = "health-inbody-agent",
    conversation_id=None,
    deadline_monotonic: Optional[float] = None,
    cancel_event: Any = None,
    chat_fn: Optional[Callable] = None,
) -> dict:
    if chat_fn is None:
        from api.dependencies import get_chat_runner
        chat_fn = get_chat_runner()
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


_UNSET = object()


def _poll_celery_task_lane(task_id: str, async_result_cls: Any) -> tuple:
    if async_result_cls is None:
        raise CeleryBackendUnavailableError("Celery result backend unavailable")
    try:
        task_result = async_result_cls(task_id)
        task_status = task_result.status
    except Exception as exc:
        raise CeleryBackendUnavailableError("Celery result backend unavailable") from exc
    if task_status == "SUCCESS":
        return task_status, task_result.result
    return task_status, None


def format_agent_response(
    response: Dict[str, Any],
    request_started: float,
) -> Dict[str, Any]:
    """Formats raw agent/composer response into standardized response schema."""
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


class ChatService:
    """Orchestrates synchronous chat execution, async Celery dispatch, and result polling."""

    def __init__(
        self,
        chat_fn: Any = _UNSET,
        store: Any = _UNSET,
        llm_handler: Any = _UNSET,
        async_result_cls: Any = _UNSET,
    ):
        self._chat_fn = chat_fn
        self._store = store
        self._llm_handler = llm_handler
        self._async_result_cls = async_result_cls

    def _get_chat_fn(self) -> Callable:
        if self._chat_fn is not _UNSET:
            return self._chat_fn
        from api.dependencies import get_chat_runner
        return get_chat_runner()

    def _get_store(self) -> Any:
        if self._store is not _UNSET:
            return self._store
        from api.dependencies import get_memory_store
        return get_memory_store()

    def _get_llm_handler(self) -> Any:
        if self._llm_handler is not _UNSET:
            return self._llm_handler
        from api.dependencies import get_llm_handler
        return get_llm_handler()

    def _get_async_result_cls(self) -> Optional[Any]:
        if self._async_result_cls is not _UNSET:
            return self._async_result_cls
        from api.dependencies import get_async_result_cls
        return get_async_result_cls()

    async def execute_sync_chat(
        self,
        question: str,
        subject: str,
        *,
        bot_id: str = "health-inbody-agent",
        conversation_id: Optional[str] = None,
        budget: Optional[RequestBudget] = None,
        urgent: bool = False,
    ) -> Dict[str, Any]:
        """Executes a chat completion synchronously. Urgent requests bypass threadpool lane."""
        chat_fn = self._get_chat_fn()
        if urgent:
            return _execute(
                call_with_supported_kwargs,
                chat_fn,
                question,
                subject,
                bot_id=bot_id,
                conversation_id=None,
            )

        effective_budget = budget or RequestBudget.start(timeout_seconds=60.0, max_timeout_seconds=120.0)
        return await get_lane("chat").run(
            _run_chat_in_lane,
            question,
            subject,
            bot_id=bot_id,
            conversation_id=conversation_id,
            deadline_monotonic=effective_budget.deadline_monotonic,
            budget=effective_budget,
            chat_fn=chat_fn,
        )

    async def dispatch_async_chat(
        self,
        question: str,
        subject: str,
        *,
        bot_id: str = "health-inbody-agent",
        conversation_id: Optional[str] = None,
        budget: Optional[RequestBudget] = None,
        queue_expires: Optional[float] = None,
    ) -> str:
        """Dispatches chat execution to the Celery background queue, returning a task_id."""
        llm_handler = self._get_llm_handler()
        if not hasattr(llm_handler, "apply_async"):
            raise QueueUnavailableError(
                "Hàng đợi hội thoại hiện không khả dụng; vui lòng dùng sync_request=true."
            )

        effective_budget = budget or RequestBudget.start(timeout_seconds=60.0, max_timeout_seconds=120.0)
        store = self._get_store()
        if conversation_id:
            await get_lane("probe").run(
                _execute,
                store.load_history,
                subject,
                str(conversation_id),
                budget=effective_budget,
                pass_cancel_event=False,
            )

        task_id = await get_lane("probe").run(
            _execute,
            store.create_task,
            subject,
            budget=effective_budget,
            pass_cancel_event=False,
        )

        expires = queue_expires if queue_expires is not None else 60.0
        deadline_epoch = time.time() + float(expires)

        await get_lane("probe").run(
            llm_handler.apply_async,
            args=[
                bot_id,
                subject,
                question,
                str(conversation_id) if conversation_id else None,
            ],
            task_id=task_id,
            expires=expires,
            kwargs={"task_id": task_id, "deadline_epoch": deadline_epoch},
            argsrepr="[redacted chat arguments]",
            kwargsrepr="{redacted task metadata}",
            budget=effective_budget,
            pass_cancel_event=False,
        )
        return str(task_id)

    async def poll_task_status(
        self,
        task_id: str,
        subject: str,
        *,
        wait: bool = True,
        hold_limit: float = 10.0,
        budget: Optional[RequestBudget] = None,
        polling_interval: float = 0.5,
    ) -> ChatPollResult:
        """Polls Celery backend for completion of an asynchronous chat task with bounded hold."""
        effective_budget = budget or RequestBudget.start(
            timeout_seconds=max(hold_limit + 5.0, 15.0),
            max_timeout_seconds=60.0,
        )
        store = self._get_store()
        await get_lane("probe").run(
            _execute,
            store.require_task_owner,
            subject,
            task_id,
            budget=effective_budget,
            pass_cancel_event=False,
        )

        async_result_cls = self._get_async_result_cls()
        if async_result_cls is None:
            raise CeleryBackendUnavailableError("Celery result backend unavailable")

        while True:
            try:
                task_status, task_result_value = await get_lane("probe").run(
                    _poll_celery_task_lane,
                    task_id,
                    async_result_cls,
                    budget=effective_budget,
                    pass_cancel_event=False,
                )
            except BudgetExhaustedError:
                return ChatPollResult(
                    task_id=task_id,
                    status="STARTED",
                    result=None,
                    retry_after="1",
                    is_ready=False,
                )

            if task_status in {"PENDING", "STARTED", "RETRY"}:
                if not wait or effective_budget.exhausted():
                    return ChatPollResult(
                        task_id=task_id,
                        status=task_status,
                        result=None,
                        retry_after="1",
                        is_ready=False,
                    )
                remaining = effective_budget.remaining_seconds()
                if remaining <= 0.0:
                    return ChatPollResult(
                        task_id=task_id,
                        status=task_status,
                        result=None,
                        retry_after="1",
                        is_ready=False,
                    )
                await asyncio.sleep(min(polling_interval, remaining))
                continue

            if task_status != "SUCCESS":
                raise TaskExecutionFailedError("Không thể hoàn thành yêu cầu hội thoại")

            return ChatPollResult(
                task_id=task_id,
                status=task_status,
                result=task_result_value,
                is_ready=True,
            )

    async def execute_agent_answer(
        self,
        question: str,
        subject: str,
        *,
        conversation_id: Optional[str] = None,
        budget: Optional[RequestBudget] = None,
        request_started: Optional[float] = None,
        urgent: bool = False,
    ) -> Dict[str, Any]:
        """Executes full agent answer orchestration, returning formatted agent response schema."""
        start_time = request_started if request_started is not None else time.perf_counter()
        raw_response = await self.execute_sync_chat(
            question,
            subject,
            conversation_id=conversation_id,
            budget=budget,
            urgent=urgent,
        )
        return format_agent_response(raw_response, start_time)

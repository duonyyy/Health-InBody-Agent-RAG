"""Shared API utilities, environment helpers, rate-limiting, and error handling."""

import os
import sys
import time
from typing import Any, Optional, Tuple

from fastapi import HTTPException, Request

from agents.constants import AGENT_MAX_REQUEST_TIMEOUT_SECONDS, AGENT_REQUEST_TIMEOUT_SECONDS
from auth.context import CurrentUser, auth_mode, get_optional_current_user
from core.execution import (
    CapacityExceededError,
    QueueTimeoutError,
    get_lane,
)
from core.rate_limit import (
    RateLimitExceededError,
    RateLimiterUnavailableError,
    enforce_rate_limit,
)
from harness.budget import BudgetExhaustedError, RequestBudget

TASK_TIMEOUT = 50
POLLING_INTERVAL = 0.5
DEFAULT_SEARCH_MAX_QUERY_CHARS = 500
DEFAULT_SUMMARIZE_MAX_TEXT_CHARS = 12000
DEFAULT_INDEX_MAX_BATCH_DOCS = 50
DEFAULT_INDEX_MAX_BATCH_CHARS = 250000


def get_app_dep(name: str, default: Any) -> Any:
    """Dynamically look up a dependency from api.app if overridden (e.g. by monkeypatch in tests)."""
    app_mod = sys.modules.get("api.app")
    if app_mod is not None and hasattr(app_mod, name):
        return getattr(app_mod, name)
    return default


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


def _resolve_expensive_caller(request: Request) -> Tuple[Optional[CurrentUser], str]:
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
    rate_limit_fn = get_app_dep("enforce_rate_limit", enforce_rate_limit)
    try:
        await get_lane("probe").run(
            rate_limit_fn,
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

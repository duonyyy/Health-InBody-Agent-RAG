"""Unified monotonic deadline, budget arithmetic, and retry classification.

No patient/health payloads are ever logged from this module.
"""

from dataclasses import dataclass
import inspect
import time
from typing import Any, Callable, Optional


class BudgetExhaustedError(TimeoutError):
    """Raised when a request's monotonic deadline has no usable time left."""


@dataclass(frozen=True)
class RequestBudget:
    """Immutable monotonic-clock deadline shared across all stages of a request."""

    deadline_monotonic: float
    total_timeout_seconds: float
    started_monotonic: float

    @classmethod
    def start(
        cls,
        timeout_seconds: float,
        *,
        max_timeout_seconds: Optional[float] = None,
        now: Optional[float] = None,
    ) -> "RequestBudget":
        current = time.monotonic() if now is None else float(now)
        effective = max(0.0, float(timeout_seconds))
        if max_timeout_seconds is not None:
            effective = min(effective, max(0.0, float(max_timeout_seconds)))
        return cls(
            deadline_monotonic=current + effective,
            total_timeout_seconds=effective,
            started_monotonic=current,
        )

    @classmethod
    def from_deadline(
        cls,
        deadline_monotonic: float,
        *,
        max_timeout_seconds: Optional[float] = None,
        total_timeout_seconds: Optional[float] = None,
        now: Optional[float] = None,
    ) -> "RequestBudget":
        current = time.monotonic() if now is None else float(now)
        clamped_deadline = float(deadline_monotonic)
        if max_timeout_seconds is not None:
            ceiling = current + max(0.0, float(max_timeout_seconds))
            clamped_deadline = min(clamped_deadline, ceiling)
        remaining = max(0.0, clamped_deadline - current)
        total = remaining if total_timeout_seconds is None else max(0.0, float(total_timeout_seconds))
        return cls(
            deadline_monotonic=clamped_deadline,
            total_timeout_seconds=total,
            started_monotonic=current,
        )

    def remaining_seconds(self, *, now: Optional[float] = None) -> float:
        current = time.monotonic() if now is None else float(now)
        return max(0.0, self.deadline_monotonic - current)

    def elapsed_seconds(self, *, now: Optional[float] = None) -> float:
        current = time.monotonic() if now is None else float(now)
        return max(0.0, current - self.started_monotonic)

    def exhausted(self, *, min_required: float = 0.0, now: Optional[float] = None) -> bool:
        return self.remaining_seconds(now=now) <= max(0.0, float(min_required))

    def bounded_timeout(
        self,
        configured_timeout: float,
        *,
        reserve_seconds: float = 0.0,
        min_timeout: float = 0.0,
        now: Optional[float] = None,
    ) -> Optional[float]:
        """Compute timeout <= min(configured, remaining - reserve); never rounds up."""
        remaining = self.remaining_seconds(now=now)
        usable = remaining - max(0.0, float(reserve_seconds))
        floor = max(0.0, float(min_timeout))
        if usable <= 0.0 or usable < floor:
            return None
        capped = min(max(0.0, float(configured_timeout)), usable)
        if capped <= 0.0 or capped < floor:
            return None
        return capped

    def backoff_seconds(
        self,
        base_delay: float,
        *,
        reserve_seconds: float = 0.0,
        min_after_sleep: float = 0.1,
        now: Optional[float] = None,
    ) -> Optional[float]:
        """Return bounded sleep duration that preserves reserve + min_after_sleep, or None."""
        remaining = self.remaining_seconds(now=now)
        available = remaining - max(0.0, float(reserve_seconds)) - max(0.0, float(min_after_sleep))
        if available <= 0.0:
            return None
        return min(max(0.0, float(base_delay)), available)


def resolve_deadline(
    *,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    default_timeout: float = 60.0,
    max_timeout: Optional[float] = None,
    now: Optional[float] = None,
) -> float:
    """Resolve one monotonic deadline; tighter explicit timeout narrows but never extends."""
    current = time.monotonic() if now is None else float(now)
    resolved: Optional[float] = None
    if deadline_monotonic is not None:
        resolved = float(deadline_monotonic)
    if timeout is not None:
        timeout_deadline = current + max(0.0, float(timeout))
        resolved = timeout_deadline if resolved is None else min(resolved, timeout_deadline)
    if resolved is None:
        resolved = current + max(0.0, float(default_timeout))
    if max_timeout is not None:
        resolved = min(resolved, current + max(0.0, float(max_timeout)))
    return resolved


def remaining_for_call(
    deadline_monotonic: Optional[float],
    configured_timeout: Optional[float],
    *,
    default_timeout: float = 60.0,
    reserve_seconds: float = 0.0,
    min_timeout: float = 0.0,
    now: Optional[float] = None,
) -> Optional[float]:
    """Return usable transport timeout <= remaining - reserve, or None if insufficient."""
    current = time.monotonic() if now is None else float(now)
    base_timeout = float(default_timeout if configured_timeout is None else configured_timeout)
    if base_timeout <= 0.0:
        return None
    if deadline_monotonic is None:
        usable = base_timeout - max(0.0, float(reserve_seconds))
    else:
        remaining = max(0.0, float(deadline_monotonic) - current)
        usable = min(base_timeout, remaining - max(0.0, float(reserve_seconds)))
    floor = max(0.0, float(min_timeout))
    if usable <= 0.0 or usable < floor:
        return None
    return usable


def call_with_supported_kwargs(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Invoke fn forwarding only keyword arguments accepted by its signature.

    Preserves full deadline/timeout propagation to production implementations while
    remaining compatible with narrower monkeypatched stubs in unit tests.
    """
    if not kwargs:
        return fn(*args)
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(*args, **kwargs)
    params = sig.parameters
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return fn(*args, **kwargs)
    filtered = {
        key: value
        for key, value in kwargs.items()
        if key in params and params[key].kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    return fn(*args, **filtered)


def _extract_status_code(exc: Exception) -> Optional[int]:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    resp_status = getattr(response, "status_code", None)
    if isinstance(resp_status, int):
        return resp_status
    return None


def retryable_llm_error(exc: Exception) -> bool:
    """Classify transient errors eligible for bounded retry.

    Never retries budget exhaustion, authentication/authorization failures,
    or client validation errors (400/401/403/404/409/422).
    """
    if isinstance(exc, BudgetExhaustedError):
        return False
    if isinstance(exc, (PermissionError, TypeError, KeyError)):
        return False

    status_code = _extract_status_code(exc)
    if status_code is not None:
        if status_code in {429, 502, 503, 504}:
            return True
        if 400 <= status_code < 500:
            return False

    cls_name = type(exc).__name__.lower()
    if any(
        non_retryable in cls_name
        for non_retryable in (
            "authentication",
            "permission",
            "badrequest",
            "notfound",
            "unprocessable",
            "validation",
            "invalidhealthinput",
        )
    ):
        return False

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if any(
        transient in cls_name
        for transient in ("timeout", "connecterror", "connectionerror", "ratelimit", "internalserver")
    ):
        return True

    message = str(exc).lower()
    if any(token in message for token in (" 400", " 401", " 403", " 404", " 422", "unauthorized", "forbidden", "invalid api key")):
        return False
    return any(
        token in message
        for token in (" 429", " 502", " 503", " 504", "timed out", "timeout", "truncated", "empty model output")
    )

"""Bounded per-process execution lanes for isolating slow synchronous I/O.

Design properties:
- Dedicated ThreadPoolExecutor per workload lane so slow I/O (search, summarize,
  non-urgent chat, indexing, health probes) NEVER saturates AnyIO's default
  threadpool used by FastAPI sync dependencies (such as get_current_user) or
  delays urgent safety responses.
- Strict separation between concurrency limit (max_concurrency) and queue bound
  (max_queue + queue_timeout_seconds).
- Accurate accounting for abandoned workers: when an HTTP request times out or
  the client disconnects while a synchronous library call is still blocked in a
  thread, the execution permit is NOT released early. It is released exactly
  once in the worker thread's finally block when the underlying call actually
  finishes. This prevents unbounded worker spawning past max_concurrency.
- Scope: per-process (one set of lanes per Uvicorn worker process).
"""

import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import threading
import time
from typing import Any, Callable, Deque, Dict, Optional, Tuple

from harness.budget import BudgetExhaustedError, RequestBudget, call_with_supported_kwargs

logger = logging.getLogger(__name__)


class CapacityExceededError(RuntimeError):
    """Raised when a lane's concurrency and waiting queue are both full."""


class QueueTimeoutError(RuntimeError):
    """Raised when a request waits longer than the configured queue timeout."""


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, default)
    try:
        return max(minimum, int(raw))
    except ValueError:
        return max(minimum, default)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, default)
    try:
        return max(minimum, float(raw))
    except ValueError:
        return max(minimum, default)


def _consume_future_exception(fut: asyncio.Future) -> None:
    if fut.cancelled():
        return
    try:
        fut.exception()
    except Exception:
        pass


class BoundedWorkLane:
    """Per-process bounded concurrency + bounded queue + dedicated worker pool."""

    def __init__(
        self,
        name: str,
        *,
        max_concurrency: int,
        max_queue: int,
        queue_timeout_seconds: float,
    ) -> None:
        self.name = name
        self.max_concurrency = max(1, int(max_concurrency))
        self.max_queue = max(0, int(max_queue))
        self.queue_timeout_seconds = max(0.0, float(queue_timeout_seconds))
        self._lock = threading.Lock()
        self._active = 0
        self._abandoned = 0
        self._completed_total = 0
        self._rejected_total = 0
        self._timed_out_total = 0
        self._waiters: Deque[Tuple[asyncio.AbstractEventLoop, asyncio.Future]] = deque()
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_concurrency,
            thread_name_prefix=f"lane-{name}",
        )

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "lane": self.name,
                "scope": "per_process",
                "active": self._active,
                "abandoned": self._abandoned,
                "queued": len(self._waiters),
                "max_concurrency": self.max_concurrency,
                "max_queue": self.max_queue,
                "queue_timeout_seconds": self.queue_timeout_seconds,
                "completed_total": self._completed_total,
                "rejected_total": self._rejected_total,
                "timed_out_total": self._timed_out_total,
            }

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _resolve_waiter_on_loop(self, fut: asyncio.Future) -> None:
        if not fut.done():
            fut.set_result(True)
        else:
            # Waiter was cancelled between handoff and loop tick; return permit.
            self._release()

    def _release_locked(self) -> None:
        while self._waiters:
            waiter_loop, waiter_fut = self._waiters.popleft()
            if waiter_fut.done() or waiter_loop.is_closed():
                continue
            try:
                waiter_loop.call_soon_threadsafe(self._resolve_waiter_on_loop, waiter_fut)
                # Permit ownership transfers directly to the waiter; _active stays unchanged.
                return
            except RuntimeError:
                continue
        self._active = max(0, self._active - 1)

    def _release(self) -> None:
        with self._lock:
            self._release_locked()

    async def _acquire(self, budget: RequestBudget) -> None:
        loop = asyncio.get_running_loop()
        if budget.exhausted():
            with self._lock:
                self._timed_out_total += 1
            raise BudgetExhaustedError(f"{self.name} budget exhausted before admission")

        waiter_fut: Optional[asyncio.Future] = None
        with self._lock:
            if self._active < self.max_concurrency and not self._waiters:
                self._active += 1
                return
            if len(self._waiters) >= self.max_queue:
                self._rejected_total += 1
                raise CapacityExceededError(f"{self.name} capacity and queue exhausted")
            waiter_fut = loop.create_future()
            self._waiters.append((loop, waiter_fut))

        wait_budget = min(self.queue_timeout_seconds, budget.remaining_seconds())
        if wait_budget <= 0.0:
            self._cancel_waiter(loop, waiter_fut)
            with self._lock:
                self._timed_out_total += 1
            raise BudgetExhaustedError(f"{self.name} budget exhausted while queuing")

        try:
            await asyncio.wait_for(waiter_fut, timeout=wait_budget)
        except asyncio.TimeoutError as exc:
            self._cancel_waiter(loop, waiter_fut)
            with self._lock:
                if budget.exhausted():
                    self._timed_out_total += 1
                    raise BudgetExhaustedError(
                        f"{self.name} request budget exhausted while waiting in queue"
                    ) from exc
                self._rejected_total += 1
            raise QueueTimeoutError(f"{self.name} queue wait timeout exceeded") from exc
        except asyncio.CancelledError:
            self._cancel_waiter(loop, waiter_fut)
            raise

    def _cancel_waiter(self, loop: asyncio.AbstractEventLoop, waiter_fut: asyncio.Future) -> None:
        handed_off = False
        with self._lock:
            try:
                self._waiters.remove((loop, waiter_fut))
            except ValueError:
                # Already popped by _release_locked; check if permit was delivered.
                handed_off = waiter_fut.done() and not waiter_fut.cancelled()
            if handed_off:
                self._release_locked()

    async def run(
        self,
        fn: Callable[..., Any],
        *args: Any,
        budget: RequestBudget,
        pass_cancel_event: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Execute blocking fn in this lane under the shared RequestBudget."""
        await self._acquire(budget)

        cancel_event = threading.Event()
        state_lock = threading.Lock()
        released = False
        abandoned = False

        def mark_abandoned() -> None:
            nonlocal abandoned
            with state_lock:
                if released or abandoned:
                    return
                abandoned = True
            with self._lock:
                self._abandoned += 1

        def release_once(completed: bool) -> None:
            nonlocal released
            was_abandoned = False
            with state_lock:
                if released:
                    return
                released = True
                was_abandoned = abandoned
            with self._lock:
                if was_abandoned:
                    self._abandoned = max(0, self._abandoned - 1)
                if completed and not was_abandoned:
                    self._completed_total += 1
                self._release_locked()

        if budget.exhausted():
            release_once(completed=False)
            with self._lock:
                self._timed_out_total += 1
            raise BudgetExhaustedError(f"{self.name} budget exhausted before worker start")

        call_kwargs = dict(kwargs)
        if pass_cancel_event:
            call_kwargs.setdefault("cancel_event", cancel_event)

        def worker() -> Any:
            completed = False
            try:
                if cancel_event.is_set() or budget.exhausted():
                    raise BudgetExhaustedError(
                        f"{self.name} cancelled or deadline exhausted before execution"
                    )
                result = call_with_supported_kwargs(fn, *args, **call_kwargs)
                completed = not cancel_event.is_set()
                return result
            finally:
                release_once(completed=completed)

        loop = asyncio.get_running_loop()
        try:
            work_future = loop.run_in_executor(self._executor, worker)
        except Exception:
            release_once(completed=False)
            raise

        work_future.add_done_callback(_consume_future_exception)
        remaining = budget.remaining_seconds()
        if remaining <= 0.0:
            cancel_event.set()
            mark_abandoned()
            with self._lock:
                self._timed_out_total += 1
            raise BudgetExhaustedError(f"{self.name} budget exhausted after dispatch")

        try:
            return await asyncio.wait_for(asyncio.shield(work_future), timeout=remaining)
        except asyncio.TimeoutError as exc:
            cancel_event.set()
            mark_abandoned()
            with self._lock:
                self._timed_out_total += 1
            raise BudgetExhaustedError(f"{self.name} exceeded request deadline") from exc
        except asyncio.CancelledError:
            cancel_event.set()
            mark_abandoned()
            raise


_LANE_DEFAULTS: Dict[str, Tuple[str, int, str, int, str, float]] = {
    "chat": (
        "CHAT_MAX_CONCURRENCY", 4,
        "CHAT_MAX_QUEUE", 8,
        "CHAT_QUEUE_TIMEOUT_SECONDS", 5.0,
    ),
    "search": (
        "SEARCH_MAX_CONCURRENCY", 4,
        "SEARCH_MAX_QUEUE", 8,
        "SEARCH_QUEUE_TIMEOUT_SECONDS", 3.0,
    ),
    "summarize": (
        "SUMMARIZE_MAX_CONCURRENCY", 2,
        "SUMMARIZE_MAX_QUEUE", 4,
        "SUMMARIZE_QUEUE_TIMEOUT_SECONDS", 3.0,
    ),
    "indexing": (
        "INDEXING_MAX_CONCURRENCY", 1,
        "INDEXING_MAX_QUEUE", 2,
        "INDEXING_QUEUE_TIMEOUT_SECONDS", 3.0,
    ),
    "probe": (
        "PROBE_MAX_CONCURRENCY", 4,
        "PROBE_MAX_QUEUE", 4,
        "PROBE_QUEUE_TIMEOUT_SECONDS", 2.0,
    ),
}

_LANES_LOCK = threading.Lock()
_LANES: Dict[str, BoundedWorkLane] = {}


def get_lane(name: str) -> BoundedWorkLane:
    with _LANES_LOCK:
        lane = _LANES.get(name)
        if lane is not None:
            return lane
        spec = _LANE_DEFAULTS.get(name)
        if spec is None:
            raise KeyError(f"Unknown execution lane: {name}")
        conc_env, conc_def, queue_env, queue_def, wait_env, wait_def = spec
        lane = BoundedWorkLane(
            name,
            max_concurrency=_env_int(conc_env, conc_def, minimum=1),
            max_queue=_env_int(queue_env, queue_def, minimum=0),
            queue_timeout_seconds=_env_float(wait_env, wait_def, minimum=0.05),
        )
        _LANES[name] = lane
        return lane


def configure_lane(
    name: str,
    *,
    max_concurrency: int,
    max_queue: int,
    queue_timeout_seconds: float,
) -> BoundedWorkLane:
    """Replace one lane (primarily for isolated tests and runtime tuning)."""
    with _LANES_LOCK:
        old = _LANES.pop(name, None)
        if old is not None:
            old.shutdown(wait=False)
        lane = BoundedWorkLane(
            name,
            max_concurrency=max_concurrency,
            max_queue=max_queue,
            queue_timeout_seconds=queue_timeout_seconds,
        )
        _LANES[name] = lane
        return lane


def reset_lanes(*, wait: bool = False) -> None:
    with _LANES_LOCK:
        lanes = list(_LANES.values())
        _LANES.clear()
    for lane in lanes:
        lane.shutdown(wait=wait)


def get_all_lane_stats() -> Dict[str, Dict[str, Any]]:
    with _LANES_LOCK:
        names = list(_LANES.keys())
    return {name: get_lane(name).stats() for name in names}

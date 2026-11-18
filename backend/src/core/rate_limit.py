"""Rate limiting distinct from concurrency/queue admission.

Deployment scope:
- When Valkey/Redis is reachable: deployment-wide fixed window enforced
  atomically with a single Lua script (INCR + EXPIRE in one round trip).
- When Valkey/Redis is offline:
  - Production (AUTH_MODE=production and RATE_LIMIT_FAIL_CLOSED_IN_PRODUCTION=true):
    fail closed with RateLimiterUnavailableError (HTTP 503) for expensive
    non-urgent endpoints.
  - Development (or explicit fail-open override): falls back to a thread-safe
    in-memory per-process counter explicitly tagged scope="per_process".

Invariant:
- Urgent safety fast-path MUST NEVER call this module.
"""

from dataclasses import dataclass
import hashlib
import logging
import math
import os
import threading
import time
from typing import Dict, Optional, Tuple

from auth.context import auth_mode
from core.cache import get_redis_client

logger = logging.getLogger(__name__)

_ATOMIC_FIXED_WINDOW_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
    ttl = tonumber(ARGV[1])
end
return {current, ttl}
"""


class RateLimitExceededError(RuntimeError):
    """Raised when a caller exceeds the configured request rate."""

    def __init__(self, message: str, *, retry_after_seconds: int = 60, scope: str = "per_process") -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        self.scope = scope


class RateLimiterUnavailableError(RuntimeError):
    """Raised in production when the distributed rate limiter cannot be reached."""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int
    scope: str  # "deployment" | "per_process" | "disabled"


_LOCAL_LOCK = threading.Lock()
_LOCAL_COUNTERS: Dict[str, Tuple[int, float]] = {}
_LOCAL_MAX_KEYS = 4096


def reset_local_rate_limits() -> None:
    with _LOCAL_LOCK:
        _LOCAL_COUNTERS.clear()


def _fail_closed_in_production() -> bool:
    return os.getenv("RATE_LIMIT_FAIL_CLOSED_IN_PRODUCTION", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _rate_limit_enabled() -> bool:
    return os.getenv("API_RATE_LIMIT_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _hash_identifier(bucket: str, identifier: str) -> str:
    digest = hashlib.sha256(f"{bucket}:{identifier}".encode("utf-8")).hexdigest()
    return f"bodywise:ratelimit:{bucket}:{digest}"


def _check_redis(client: object, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
    if hasattr(client, "eval"):
        result = client.eval(_ATOMIC_FIXED_WINDOW_LUA, 1, key, int(window_seconds))
        count = int(result[0])
        ttl = int(result[1]) if len(result) > 1 and int(result[1]) > 0 else int(window_seconds)
    else:
        # Fallback for simplified mock Redis clients without eval()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, int(window_seconds))
        ttl = int(window_seconds)
    return RateLimitDecision(
        allowed=count <= limit,
        count=count,
        limit=limit,
        retry_after_seconds=max(1, ttl),
        scope="deployment",
    )


def _check_local(key: str, limit: int, window_seconds: int) -> RateLimitDecision:
    now = time.monotonic()
    with _LOCAL_LOCK:
        if len(_LOCAL_COUNTERS) >= _LOCAL_MAX_KEYS:
            expired = [k for k, (_, exp) in _LOCAL_COUNTERS.items() if exp <= now]
            for k in expired:
                _LOCAL_COUNTERS.pop(k, None)
            if len(_LOCAL_COUNTERS) >= _LOCAL_MAX_KEYS:
                _LOCAL_COUNTERS.clear()

        count, expires_at = _LOCAL_COUNTERS.get(key, (0, 0.0))
        if expires_at <= now:
            count = 1
            expires_at = now + float(window_seconds)
        else:
            count += 1
        _LOCAL_COUNTERS[key] = (count, expires_at)
        retry_after = max(1, int(math.ceil(expires_at - now)))
    return RateLimitDecision(
        allowed=count <= limit,
        count=count,
        limit=limit,
        retry_after_seconds=retry_after,
        scope="per_process",
    )


def enforce_rate_limit(
    *,
    bucket: str,
    identifier: str,
    limit: int,
    window_seconds: int = 60,
    redis_client: Optional[object] = None,
) -> RateLimitDecision:
    """Enforce a fixed-window rate limit for one non-urgent endpoint bucket."""
    if not _rate_limit_enabled() or limit <= 0:
        return RateLimitDecision(
            allowed=True,
            count=0,
            limit=max(0, int(limit)),
            retry_after_seconds=0,
            scope="disabled",
        )

    key = _hash_identifier(bucket, identifier)
    client = redis_client if redis_client is not None else get_redis_client()
    if client is not None:
        try:
            decision = _check_redis(client, key, int(limit), int(window_seconds))
        except Exception as exc:
            logger.warning("Distributed rate limiter error for bucket=%s (%s)", bucket, type(exc).__name__)
            if auth_mode() == "production" and _fail_closed_in_production():
                raise RateLimiterUnavailableError(
                    "Hệ thống kiểm soát lưu lượng tạm thời không khả dụng. Vui lòng thử lại sau."
                ) from exc
            decision = _check_local(key, int(limit), int(window_seconds))
    else:
        if auth_mode() == "production" and _fail_closed_in_production():
            raise RateLimiterUnavailableError(
                "Hệ thống kiểm soát lưu lượng tạm thời không khả dụng. Vui lòng thử lại sau."
            )
        decision = _check_local(key, int(limit), int(window_seconds))

    if not decision.allowed:
        raise RateLimitExceededError(
            "Bạn gửi yêu cầu quá nhanh. Vui lòng chờ và thử lại.",
            retry_after_seconds=decision.retry_after_seconds,
            scope=decision.scope,
        )
    return decision

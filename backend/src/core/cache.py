"""Cache utilities cho Health/InBody Agent RAG."""
import json
import logging
import os
import time
from collections import OrderedDict
import threading
from threading import RLock
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "valkey-db")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
CACHE_NAMESPACE = os.environ.get("CACHE_NAMESPACE", "health_inbody")
CACHE_MEMORY_MAX_ENTRIES = max(1, int(os.environ.get("CACHE_MEMORY_MAX_ENTRIES", "256")))
CACHE_REDIS_RETRY_SECONDS = max(1.0, float(os.environ.get("CACHE_REDIS_RETRY_SECONDS", "15")))
CACHE_REDIS_CONNECT_TIMEOUT_SECONDS = max(
    0.1, float(os.environ.get("CACHE_REDIS_CONNECT_TIMEOUT_SECONDS", "1.0"))
)
CACHE_REDIS_SOCKET_TIMEOUT_SECONDS = max(
    0.1, float(os.environ.get("CACHE_REDIS_SOCKET_TIMEOUT_SECONDS", "1.0"))
)
LLM_RESPONSE_CACHE_TTL_SECONDS = max(
    1, int(os.environ.get("LLM_RESPONSE_CACHE_TTL_SECONDS", "300"))
)

_redis_client = None
_redis_last_attempt = 0.0
_redis_probe_lock = threading.Lock()
_redis_probe_in_flight = False
_memory_cache = OrderedDict()
_cache_lock = RLock()
_llm_response_cache_stats = {"hits": 0, "misses": 0, "writes": 0, "invalidations": 0, "errors": 0}


def _now() -> float:
    return time.time()


def _namespaced_key(*parts) -> str:
    clean_parts = [str(part).strip().replace(" ", "_") for part in parts if part is not None]
    return ":".join([CACHE_NAMESPACE] + clean_parts)


def get_redis_client(timeout: Optional[float] = None):
    """
    Lay Redis client neu Redis va package redis san sang.

    Bao ve bang single-flight daemon probe de DNS lookup (socket.getaddrinfo)
    cham khong bao gio chan request thread qua connect timeout.
    """
    global _redis_client, _redis_last_attempt, _redis_probe_in_flight

    if _redis_client is not None:
        return _redis_client

    wait_budget = CACHE_REDIS_CONNECT_TIMEOUT_SECONDS
    if timeout is not None:
        wait_budget = min(wait_budget, max(0.0, float(timeout)))
    if wait_budget <= 0.0:
        return None

    done_event = threading.Event()
    with _redis_probe_lock:
        if _redis_client is not None:
            return _redis_client
        now = time.monotonic()
        if _redis_probe_in_flight or (
            _redis_last_attempt > 0.0 and (now - _redis_last_attempt) < CACHE_REDIS_RETRY_SECONDS
        ):
            return None
        _redis_probe_in_flight = True
        _redis_last_attempt = now

    def _probe() -> None:
        global _redis_client, _redis_last_attempt, _redis_probe_in_flight
        try:
            import redis

            client = redis.StrictRedis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                socket_connect_timeout=CACHE_REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=CACHE_REDIS_SOCKET_TIMEOUT_SECONDS,
            )
            client.ping()
            with _redis_probe_lock:
                _redis_client = client
            logger.info("Redis cache connected at %s:%s/%s", REDIS_HOST, REDIS_PORT, REDIS_DB)
        except Exception as e:
            logger.warning("Redis cache unavailable, using in-memory fallback: %s", type(e).__name__)
            with _redis_probe_lock:
                _redis_client = None
        finally:
            with _redis_probe_lock:
                _redis_last_attempt = time.monotonic()
                _redis_probe_in_flight = False
            done_event.set()

    thread = threading.Thread(target=_probe, name="redis-connect-probe", daemon=True)
    thread.start()
    if not done_event.wait(timeout=wait_budget):
        logger.warning(
            "Redis cache connect probe timed out after %.2fs; using fallback",
            wait_budget,
        )
        return None

    return _redis_client


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """
    Luu gia tri vao cache Redis hoac in-memory fallback.
    """
    namespaced = _namespaced_key(key)
    payload = json.dumps(value, ensure_ascii=False)
    client = get_redis_client()

    if client is not None:
        try:
            client.set(namespaced, payload, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.warning("Redis set failed, falling back to memory: %s", e)

    with _cache_lock:
        _memory_cache[namespaced] = {
            "value": payload,
            "expires_at": _now() + ttl_seconds if ttl_seconds else None,
        }
        _memory_cache.move_to_end(namespaced)
        while len(_memory_cache) > CACHE_MEMORY_MAX_ENTRIES:
            _memory_cache.popitem(last=False)
    return True


def cache_get(key: str, default: Any = None) -> Any:
    """
    Doc gia tri tu cache.
    """
    namespaced = _namespaced_key(key)
    client = get_redis_client()

    if client is not None:
        try:
            cached = client.get(namespaced)
            if cached is None:
                return default
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            return json.loads(cached)
        except Exception as e:
            logger.warning("Redis get failed, checking memory fallback: %s", e)

    with _cache_lock:
        cached_item = _memory_cache.get(namespaced)
        if not cached_item:
            return default

        expires_at = cached_item.get("expires_at")
        if expires_at and expires_at < _now():
            _memory_cache.pop(namespaced, None)
            return default

        _memory_cache.move_to_end(namespaced)
        return json.loads(cached_item["value"])


def cache_delete(key: str) -> bool:
    """
    Xoa key trong cache.
    """
    namespaced = _namespaced_key(key)
    client = get_redis_client()

    if client is not None:
        try:
            client.delete(namespaced)
        except Exception as e:
            logger.warning("Redis delete failed: %s", e)

    with _cache_lock:
        _memory_cache.pop(namespaced, None)
    return True


def cache_health_check() -> dict:
    """
    Tra ve trang thai cache de debug.
    """
    client = get_redis_client()
    return {
        "namespace": CACHE_NAMESPACE,
        "backend": "redis" if client is not None else "memory",
        "memory_keys": len(_memory_cache),
        "memory_max_entries": CACHE_MEMORY_MAX_ENTRIES,
        "llm_response_cache": {
            "enabled": llm_response_cache_enabled(),
            "ttl_seconds": LLM_RESPONSE_CACHE_TTL_SECONDS,
            **_llm_response_cache_stats,
        },
    }


def llm_response_cache_enabled() -> bool:
    """Return whether the narrowly scoped public RAG response cache is enabled."""
    return os.environ.get("LLM_RESPONSE_CACHE_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }


def llm_response_cache_get(key: str) -> Optional[str]:
    """Read one exact-match composer response, recording only aggregate metrics."""
    if not llm_response_cache_enabled():
        return None
    try:
        value = cache_get(key)
    except Exception as exc:
        _llm_response_cache_stats["errors"] += 1
        logger.warning("LLM response cache read failed (%s)", type(exc).__name__)
        return None
    if isinstance(value, str) and value.strip():
        _llm_response_cache_stats["hits"] += 1
        return value
    _llm_response_cache_stats["misses"] += 1
    return None


def llm_response_cache_set(key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
    """Store a validated public composer response under a versioned opaque key."""
    if not llm_response_cache_enabled() or not isinstance(value, str) or not value.strip():
        return False
    try:
        stored = cache_set(
            key,
            value,
            ttl_seconds=ttl_seconds or LLM_RESPONSE_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        _llm_response_cache_stats["errors"] += 1
        logger.warning("LLM response cache write failed (%s)", type(exc).__name__)
        return False
    if stored:
        _llm_response_cache_stats["writes"] += 1
    return stored


def llm_response_cache_delete(key: str) -> bool:
    """Evict a cached response that fails the current output/evidence guards."""
    try:
        deleted = cache_delete(key)
    except Exception as exc:
        _llm_response_cache_stats["errors"] += 1
        logger.warning("LLM response cache invalidation failed (%s)", type(exc).__name__)
        return False
    _llm_response_cache_stats["invalidations"] += 1
    return deleted

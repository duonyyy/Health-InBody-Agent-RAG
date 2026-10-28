"""Cache utilities cho Health/InBody Agent RAG."""
import json
import logging
import os
import time
from collections import OrderedDict
from threading import RLock
from typing import Any, Optional

from core.utils import generate_request_id

logger = logging.getLogger(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "valkey-db")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
CACHE_NAMESPACE = os.environ.get("CACHE_NAMESPACE", "health_inbody")
CACHE_MEMORY_MAX_ENTRIES = max(1, int(os.environ.get("CACHE_MEMORY_MAX_ENTRIES", "256")))
CACHE_REDIS_RETRY_SECONDS = max(1.0, float(os.environ.get("CACHE_REDIS_RETRY_SECONDS", "5")))
LLM_RESPONSE_CACHE_TTL_SECONDS = max(
    1, int(os.environ.get("LLM_RESPONSE_CACHE_TTL_SECONDS", "300"))
)

_redis_client = None
_redis_last_attempt = 0.0
_memory_cache = OrderedDict()
_cache_lock = RLock()
_llm_response_cache_stats = {"hits": 0, "misses": 0, "writes": 0, "invalidations": 0, "errors": 0}


def _now() -> float:
    return time.time()


def _namespaced_key(*parts) -> str:
    clean_parts = [str(part).strip().replace(" ", "_") for part in parts if part is not None]
    return ":".join([CACHE_NAMESPACE] + clean_parts)


def get_redis_client():
    """
    Lay Redis client neu Redis va package redis san sang.

    Ham lazy-load de module van import duoc trong moi truong dev chua cai Redis.
    """
    global _redis_client, _redis_last_attempt

    if _redis_client is not None:
        return _redis_client
    now = time.monotonic()
    if now - _redis_last_attempt < CACHE_REDIS_RETRY_SECONDS:
        return None
    _redis_last_attempt = now
    try:
        import redis

        client = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis cache connected at %s:%s/%s", REDIS_HOST, REDIS_PORT, REDIS_DB)
    except Exception as e:
        logger.warning("Redis cache unavailable, using in-memory fallback: %s", e)
        _redis_client = None

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


def get_conversation_key(bot_id, user_id):
    """Tao key conversation theo namespace Health/InBody."""
    return _namespaced_key("conversation", bot_id, user_id)


def get_conversation_id(bot_id, user_id, ttl_seconds=3600):
    """
    Lay conversation_id tu cache, neu chua co thi tao moi.
    """
    key = get_conversation_key(bot_id, user_id)
    conversation_id = cache_get(key)
    if conversation_id:
        cache_set(key, conversation_id, ttl_seconds=ttl_seconds)
        return conversation_id

    conversation_id = generate_request_id()
    cache_set(key, conversation_id, ttl_seconds=ttl_seconds)
    return conversation_id


def clear_conversation_id(bot_id, user_id):
    """Xoa conversation_id cua nguoi dung."""
    key = get_conversation_key(bot_id, user_id)
    return cache_delete(key)


def get_rag_cache_key(query: str, user_id: Optional[str] = None) -> str:
    """Tao key cache cho retrieval/query Health RAG."""
    return _namespaced_key("rag", user_id or "anonymous", query.lower().strip())


def get_embedding_cache_key(text: str) -> str:
    """Tao key cache cho embedding text/chunk."""
    return _namespaced_key("embedding", hash(text))

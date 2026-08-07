"""Cache utilities cho Health/InBody Agent RAG."""
import json
import logging
import os
import time
from typing import Any, Optional

from core.utils import generate_request_id

logger = logging.getLogger(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "valkey-db")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
CACHE_NAMESPACE = os.environ.get("CACHE_NAMESPACE", "health_inbody")

_redis_client = None
_redis_checked = False
_memory_cache = {}


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
    global _redis_client, _redis_checked

    if _redis_checked:
        return _redis_client

    _redis_checked = True
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

    _memory_cache[namespaced] = {
        "value": payload,
        "expires_at": _now() + ttl_seconds if ttl_seconds else None,
    }
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

    cached_item = _memory_cache.get(namespaced)
    if not cached_item:
        return default

    expires_at = cached_item.get("expires_at")
    if expires_at and expires_at < _now():
        _memory_cache.pop(namespaced, None)
        return default

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
    }


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

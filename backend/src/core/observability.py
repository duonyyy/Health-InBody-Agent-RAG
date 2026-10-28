"""Observability and distributed tracing module for Health/InBody Agent RAG.

Integrates with Langfuse for full-stack LLM observability (traces, spans,
generations, token usage, cost tracking, and quality feedback).
Includes zero-overhead dummy fallbacks when Langfuse SDK is unavailable,
disabled via environment variables, or running in offline unit tests.
Adheres strictly to health data privacy and PII protection rules.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# ==============================================================================
# Configuration Defaults
# ==============================================================================
LANGFUSE_ENABLED_ENV = os.getenv("LANGFUSE_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip()
LANGFUSE_ENV = os.getenv("LANGFUSE_ENV", "development").strip()
LANGFUSE_MASK_HEALTH_PII = os.getenv("LANGFUSE_MASK_HEALTH_PII", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LANGFUSE_ID_SALT = os.getenv("LANGFUSE_ID_SALT", "health_inbody_salt_2026").strip()

# ==============================================================================
# Dummy Fallback Classes (Graceful Degradation)
# ==============================================================================
class _DummySpan:
    """No-op span used when Langfuse is disabled or unavailable."""

    def __init__(self, id_str: str = "dummy-span-id") -> None:
        self.id = id_str

    def span(self, **kwargs: Any) -> _DummySpan:
        return self

    def generation(self, **kwargs: Any) -> _DummyGeneration:
        return _DummyGeneration()

    def event(self, **kwargs: Any) -> None:
        return None

    def end(self, **kwargs: Any) -> None:
        return None

    def update(self, **kwargs: Any) -> _DummySpan:
        return self


class _DummyGeneration:
    """No-op generation used when Langfuse is disabled or unavailable."""

    def __init__(self, id_str: str = "dummy-gen-id") -> None:
        self.id = id_str

    def end(self, **kwargs: Any) -> None:
        return None

    def update(self, **kwargs: Any) -> _DummyGeneration:
        return self


class _DummyTrace:
    """No-op trace used when Langfuse is disabled or unavailable."""

    def __init__(self, id_str: str = "dummy-trace-id") -> None:
        self.id = id_str

    def span(self, **kwargs: Any) -> _DummySpan:
        return _DummySpan()

    def generation(self, **kwargs: Any) -> _DummyGeneration:
        return _DummyGeneration()

    def event(self, **kwargs: Any) -> None:
        return None

    def score(self, **kwargs: Any) -> None:
        return None

    def update(self, **kwargs: Any) -> _DummyTrace:
        return self


class _DummyClient:
    """No-op Langfuse client ensuring 0ms overhead and zero network failures."""

    def trace(self, **kwargs: Any) -> _DummyTrace:
        return _DummyTrace()

    def span(self, **kwargs: Any) -> _DummySpan:
        return _DummySpan()

    def generation(self, **kwargs: Any) -> _DummyGeneration:
        return _DummyGeneration()

    def score(self, **kwargs: Any) -> None:
        return None

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def get_prompt(self, name: str, **kwargs: Any) -> Any:
        return None


# ==============================================================================
# Langfuse SDK Initialization
# ==============================================================================
_client_instance: Optional[Any] = None
LANGFUSE_SDK_AVAILABLE: bool = False

try:
    from langfuse import Langfuse  # type: ignore

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:
    LANGFUSE_SDK_AVAILABLE = False


def is_langfuse_enabled() -> bool:
    """Check if Langfuse is both installed and configured with valid keys."""
    return (
        LANGFUSE_SDK_AVAILABLE
        and LANGFUSE_ENABLED_ENV
        and bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
    )


def get_langfuse_client() -> Any:
    """Return the singleton Langfuse client, or dummy client if disabled."""
    global _client_instance
    if not is_langfuse_enabled():
        return _DummyClient()

    if _client_instance is None:
        try:
            _client_instance = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_BASE_URL,
            )
            logger.info("Langfuse client initialized successfully for environment: %s", LANGFUSE_ENV)
        except Exception as exc:
            logger.warning("Failed to initialize Langfuse client (%s); falling back to dummy", exc)
            return _DummyClient()

    return _client_instance


# ==============================================================================
# PII Protection & User ID Hashing
# ==============================================================================
def hash_user_id(subject: Optional[str]) -> Optional[str]:
    """Hash subject with SHA-256 and salt to prevent raw user IDs from leaking to cloud tracing."""
    if not subject:
        return None
    raw = f"{LANGFUSE_ID_SALT}:{subject}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def redact_sensitive_health_data(payload: Any) -> Any:
    """Mask potentially sensitive raw fields before submitting metadata to traces."""
    if not LANGFUSE_MASK_HEALTH_PII:
        return payload

    if isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            if k in {"email", "full_name", "phone", "raw_payload"}:
                sanitized[k] = "[REDACTED_PII]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = redact_sensitive_health_data(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(payload, list):
        return [redact_sensitive_health_data(item) for item in payload]
    return payload


# ==============================================================================
# Context Management for Request Lifecycle
# ==============================================================================
_active_trace: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "active_trace", default=None
)
_active_span: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "active_span", default=None
)


def set_active_trace(trace: Any) -> None:
    _active_trace.set(trace)


def get_active_trace() -> Optional[Any]:
    return _active_trace.get()


def set_active_span(span: Any) -> None:
    _active_span.set(span)


def get_active_span() -> Optional[Any]:
    return _active_span.get()


# ==============================================================================
# Public Tracing Helpers
# ==============================================================================
def start_trace(
    name: str = "health_inbody_chat",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    input_text: Optional[str] = None,
) -> Any:
    """Create a new root trace for a chat turn or request."""
    client = get_langfuse_client()
    trace_tags = list(tags or [])
    if LANGFUSE_ENV not in trace_tags:
        trace_tags.append(LANGFUSE_ENV)

    sanitized_metadata = redact_sensitive_health_data(metadata or {})
    trace = client.trace(
        name=name,
        user_id=hash_user_id(user_id),
        session_id=str(session_id) if session_id else None,
        tags=trace_tags,
        metadata=sanitized_metadata,
        input=input_text,
    )
    set_active_trace(trace)
    return trace


@contextmanager
def trace_span(
    name: str,
    span_type: str = "agent_node",
    input_data: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[Any, None, None]:
    """Context manager to measure latency and record child spans under the current trace."""
    current_parent = get_active_span() or get_active_trace()
    started = time.perf_counter()

    sanitized_input = redact_sensitive_health_data(input_data)
    sanitized_meta = redact_sensitive_health_data(metadata or {})
    sanitized_meta["span_type"] = span_type

    if current_parent is not None and hasattr(current_parent, "span"):
        span = current_parent.span(
            name=name,
            input=sanitized_input,
            metadata=sanitized_meta,
            start_time=time.time(),
        )
    else:
        span = _DummySpan()

    previous_span = get_active_span()
    set_active_span(span)
    try:
        yield span
    except Exception as exc:
        span.update(level="ERROR", status_message=str(exc))
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        span.end(end_time=time.time(), metadata={"latency_ms": latency_ms})
        set_active_span(previous_span)


def record_generation(
    name: str,
    model: str,
    prompt_messages: Any,
    output_text: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an LLM completion generation with token usage and cost."""
    current_parent = get_active_span() or get_active_trace()
    if current_parent is None or not hasattr(current_parent, "generation"):
        return

    usage_details: Dict[str, int] = {}
    if prompt_tokens > 0 or completion_tokens > 0:
        usage_details["prompt_tokens"] = prompt_tokens
        usage_details["completion_tokens"] = completion_tokens
        usage_details["total_tokens"] = prompt_tokens + completion_tokens

    cost_details = {"total": cost_usd} if cost_usd is not None else None

    current_parent.generation(
        name=name,
        model=model,
        input=redact_sensitive_health_data(prompt_messages),
        output=output_text,
        usage=usage_details if usage_details else None,
        cost_details=cost_details,
        metadata=redact_sensitive_health_data(metadata or {}),
    )


def record_feedback(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
) -> None:
    """Submit qualitative feedback score to Langfuse."""
    client = get_langfuse_client()
    try:
        client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )
    except Exception as exc:
        logger.warning("Failed to record Langfuse score (%s)", exc)


def flush_traces() -> None:
    """Flush pending events to Langfuse."""
    client = get_langfuse_client()
    try:
        client.flush()
    except Exception as exc:
        logger.debug("Langfuse flush warning: %s", exc)

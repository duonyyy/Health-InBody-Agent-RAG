"""HTTP boundary dependency providers for FastAPI dependency injection.

Follows python-common-patterns (references/dependency-injection.md):
- Declare dependencies at HTTP/framework boundaries using FastAPI Depends.
- Enables clean unit/integration testing via app.dependency_overrides without monkeypatching sys.modules.
- Preserves backwards-compatibility with legacy test monkeypatching on api.app.
"""

import sys
from typing import Any, Callable, Optional, Type

from fastapi import Depends
from fastapi.params import Depends as DependsClass

try:
    from celery.result import AsyncResult
except Exception:
    AsyncResult = None

from jobs.tasks import llm_handle_message
from memory import store as memory_store
from memory.chat import run_chat


def _get_app_attr(name: str, default: Any) -> Any:
    """Resolve dependency, falling back to api.app attributes if monkeypatched in legacy tests."""
    app_mod = sys.modules.get("api.app")
    if app_mod is not None and hasattr(app_mod, name):
        return getattr(app_mod, name)
    return default


def get_chat_runner() -> Callable:
    """Provides the chat execution function (defaults to memory.chat.run_chat)."""
    return _get_app_attr("run_chat", run_chat)


def get_memory_store() -> Any:
    """Provides the chat memory store module/service."""
    return _get_app_attr("memory_store", memory_store)


def get_async_result_cls() -> Optional[Type]:
    """Provides Celery AsyncResult class."""
    return _get_app_attr("AsyncResult", AsyncResult)


def get_llm_handler() -> Any:
    """Provides Celery LLM task handler (defaults to jobs.tasks.llm_handle_message)."""
    return _get_app_attr("llm_handle_message", llm_handle_message)


def get_rate_limit_checker() -> Callable:
    """Provides asynchronous rate limit checking function."""
    from api.common import _check_rate_limit_async

    return _get_app_attr("_check_rate_limit_async", _check_rate_limit_async)


def get_readiness_reporter() -> Callable:
    """Provides readiness health check reporter function."""
    from api.app import _readiness_report

    return _get_app_attr("_readiness_report", _readiness_report)


def get_chat_service(
    chat_fn: Any = Depends(get_chat_runner),
    store: Any = Depends(get_memory_store),
    llm_handler: Any = Depends(get_llm_handler),
    async_result_cls: Optional[Any] = Depends(get_async_result_cls),
) -> Any:
    """Provides ChatService application service instance."""
    from fastapi.params import Depends as DependsClass
    from services.chat_service import ChatService

    service_override = _get_app_attr("chat_service", None)
    if service_override is not None:
        return service_override

    resolved_chat_fn = get_chat_runner() if (chat_fn is None or isinstance(chat_fn, DependsClass)) else chat_fn
    resolved_store = get_memory_store() if (store is None or isinstance(store, DependsClass)) else store
    resolved_llm_handler = get_llm_handler() if (llm_handler is None or isinstance(llm_handler, DependsClass)) else llm_handler
    resolved_async_result_cls = get_async_result_cls() if (async_result_cls is None or isinstance(async_result_cls, DependsClass)) else async_result_cls

    return ChatService(
        chat_fn=resolved_chat_fn,
        store=resolved_store,
        llm_handler=resolved_llm_handler,
        async_result_cls=resolved_async_result_cls,
    )


def get_ocr_http_session() -> Any:
    """Provides pooled HTTP session for OCR service."""
    from api.inbody_ocr import get_ocr_http_session as _get_ocr_session
    return _get_app_attr("ocr_http_session", _get_ocr_session())


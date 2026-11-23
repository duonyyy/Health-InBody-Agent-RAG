"""Search and summarization endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request

from api.common import (
    DEFAULT_SEARCH_MAX_QUERY_CHARS,
    DEFAULT_SUMMARIZE_MAX_TEXT_CHARS,
    _check_rate_limit_async,
    _env_int,
    _raise_lane_http_error,
    _resolve_expensive_caller,
    _search_timeout_seconds,
    _summarize_timeout_seconds,
    get_app_dep,
)
from api.schemas import SearchRequest, SummaryRequest
from core.execution import CapacityExceededError, QueueTimeoutError, get_lane
from harness.budget import BudgetExhaustedError, RequestBudget
from llm.summarizer import summarize_health_report, summarize_text
from rag.search import hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


@router.post("/search")
async def search_endpoint(data: SearchRequest, request: Request):
    query = data.query.strip()
    max_query_chars = _env_int("SEARCH_MAX_QUERY_CHARS", DEFAULT_SEARCH_MAX_QUERY_CHARS, minimum=1, maximum=2000)
    if not query or len(query) > max_query_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Truy vấn tìm kiếm không hợp lệ (tối đa {max_query_chars} ký tự).",
        )
    resolve_caller = get_app_dep("_resolve_expensive_caller", _resolve_expensive_caller)
    user, caller_id = resolve_caller(request)
    budget = RequestBudget.start(_search_timeout_seconds(), max_timeout_seconds=30.0)
    default_limit = 30 if user is not None else 60
    rate_limit = _env_int("SEARCH_RATE_LIMIT_PER_MINUTE", default_limit, minimum=0, maximum=1000)
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("search", caller_id, rate_limit, budget)
    search_fn = get_app_dep("hybrid_search", hybrid_search)
    try:
        results = await get_lane("search").run(
            search_fn,
            query,
            limit=data.limit,
            use_rerank=data.use_rerank,
            timeout=budget.remaining_seconds(),
            deadline_monotonic=budget.deadline_monotonic,
            raise_on_timeout=True,
            budget=budget,
            pass_cancel_event=False,
        )
        return {
            "query": query,
            "results": results,
        }
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        from rag.corpus_lifecycle import CorpusReleaseMismatchError
        from rag.retrieval_errors import RetrievalDependencyError

        if isinstance(exc, RetrievalDependencyError):
            raise HTTPException(status_code=503, detail={
                "reason_code": exc.reason,
                "message": "Dịch vụ tìm kiếm tạm thời không khả dụng. Vui lòng thử lại sau.",
            }) from exc

        if isinstance(exc, CorpusReleaseMismatchError):
            logger.error("Search refused due to corpus release mismatch: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Chỉ mục tìm kiếm chưa đồng bộ phiên bản corpus. Vui lòng thử lại sau khi hoàn tất phát hành.",
            ) from exc
        logger.warning("Search endpoint failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ tìm kiếm tạm thời không khả dụng. Vui lòng thử lại sau.",
        ) from exc


@router.post("/summarize")
async def summarize_endpoint(data: SummaryRequest, request: Request):
    text = data.text.strip()
    max_text_chars = _env_int(
        "SUMMARIZE_MAX_TEXT_CHARS",
        DEFAULT_SUMMARIZE_MAX_TEXT_CHARS,
        minimum=1,
        maximum=50000,
    )
    if not text or len(text) > max_text_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Nội dung cần tóm tắt không hợp lệ (tối đa {max_text_chars} ký tự).",
        )
    resolve_caller = get_app_dep("_resolve_expensive_caller", _resolve_expensive_caller)
    user, caller_id = resolve_caller(request)
    budget = RequestBudget.start(_summarize_timeout_seconds(), max_timeout_seconds=45.0)
    default_limit = 10 if user is not None else 20
    rate_limit = _env_int("SUMMARIZE_RATE_LIMIT_PER_MINUTE", default_limit, minimum=0, maximum=1000)
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("summarize", caller_id, rate_limit, budget)
    report_fn = get_app_dep("summarize_health_report", summarize_health_report)
    text_fn = get_app_dep("summarize_text", summarize_text)
    target_fn = report_fn if data.report_mode else text_fn
    try:
        summary = await get_lane("summarize").run(
            target_fn,
            text,
            timeout=budget.remaining_seconds(),
            deadline_monotonic=budget.deadline_monotonic,
            raise_on_timeout=True,
            budget=budget,
            pass_cancel_event=False,
        )
        return {"summary": summary}
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.warning("Summarize endpoint failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ tóm tắt tạm thời không khả dụng. Vui lòng thử lại sau.",
        ) from exc

"""RAG Agent: query rewriting, hybrid search, and context reranking."""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from harness.budget import (
    BudgetExhaustedError,
    call_with_supported_kwargs,
    retryable_llm_error as _retryable_llm_error,
)
from harness.layers.retry import degraded_observation
from llm.client import LLM_REWRITE_TIMEOUT
from rag.query_rewriter import rewrite_query_to_multi_queries
from rag.rerank import rerank_documents
from rag.search import hybrid_search
from ..composer import _set_evidence_state
from ..constants import (
    AGENT_COMPOSER_RESERVE_SECONDS,
    AGENT_MAX_RETRIEVAL_CALLS,
    AGENT_MIN_CALL_TIMEOUT_SECONDS,
    AGENT_RETRY_BACKOFF_SECONDS,
    INBODY_AGENT,
    NUTRITION_AGENT,
    QDRANT_SEARCH_RESERVE_SECONDS,
    RAG_AGENT,
    RAG_EMBEDDING_TIMEOUT_SECONDS,
    RAG_MAX_RETRIEVAL_QUERIES,
    RERANK_TIMEOUT_SECONDS,
    TRAINING_AGENT,
)
from ..context import (
    _backoff_seconds,
    _bounded_timeout,
    _count_call,
    _deadline_monotonic,
    _is_cancelled,
    _question,
    _remaining_seconds,
    _trace_call,
)
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def _retrieval_filters(state: AgentState) -> Optional[Dict[str, Any]]:
    """Constrain retrieval to the content types selected by the supervisor."""
    safety = state.get("safety_result") or {}
    if safety.get("risk_level") in {"urgent", "medical_caution"}:
        return {"content_type": "medical_safety"}

    selected_agents = set(state.get("selected_agents") or [])
    content_types = [
        content_type
        for agent, content_type in (
            (INBODY_AGENT, "inbody_metric"),
            (NUTRITION_AGENT, "nutrition"),
            (TRAINING_AGENT, "exercise"),
        )
        if agent in selected_agents
    ]
    if len(content_types) == 1:
        return {"content_type": content_types[0]}
    if content_types:
        return {"content_type": content_types}
    return None


def rag_agent(state: AgentState) -> AgentState:
    from .. import graph as graph_mod

    if RAG_AGENT not in state.get("selected_agents", []):
        return state

    max_queries = getattr(graph_mod, "RAG_MAX_RETRIEVAL_QUERIES", RAG_MAX_RETRIEVAL_QUERIES)
    rewrite_fn = getattr(graph_mod, "rewrite_query_to_multi_queries", rewrite_query_to_multi_queries)
    search_fn = getattr(graph_mod, "hybrid_search", hybrid_search)
    rerank_fn = getattr(graph_mod, "rerank_documents", rerank_documents)

    question = _question(state)
    deadline_monotonic = _deadline_monotonic(state)
    queries = [question]
    if _is_cancelled(state):
        append_error(state, "RAG retrieval skipped because request was cancelled")
        state["retrieved_docs"] = []
        _set_evidence_state(state, [])
        return state

    if max_queries > 1:
        rewrite_timeout = _bounded_timeout(
            state,
            LLM_REWRITE_TIMEOUT,
            AGENT_COMPOSER_RESERVE_SECONDS
            + QDRANT_SEARCH_RESERVE_SECONDS
            + RAG_EMBEDDING_TIMEOUT_SECONDS,
            min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
        )
        if rewrite_timeout >= AGENT_MIN_CALL_TIMEOUT_SECONDS:
            try:
                if not _count_call(state, "rewrite", 1):
                    raise RuntimeError("Query rewrite call budget exhausted")
                started = time.monotonic()
                rewritten = call_with_supported_kwargs(
                    rewrite_fn,
                    question,
                    num_queries=max_queries,
                    timeout=rewrite_timeout,
                    deadline_monotonic=deadline_monotonic,
                )
                queries = list(dict.fromkeys([question] + list(rewritten or [])))[:max_queries]
                _trace_call(state, RAG_AGENT, "rewrite_query", started, "success")
            except Exception as exc:
                if "started" in locals():
                    _trace_call(state, RAG_AGENT, "rewrite_query", started, "warning",
                                error_code=type(exc).__name__)
                logger.warning("Query rewrite failed (%s)", type(exc).__name__)
                append_error(state, "Query rewrite is temporarily unavailable")

    docs: List[Dict[str, Any]] = []
    seen = set()
    filters = _retrieval_filters(state)
    retrieval_reserve = AGENT_COMPOSER_RESERVE_SECONDS + QDRANT_SEARCH_RESERVE_SECONDS
    for query in queries:
        if _is_cancelled(state):
            append_error(state, "RAG retrieval cancelled before query execution")
            break
        for attempt in range(2):
            if _is_cancelled(state):
                break
            if not _count_call(state, "retrieval", AGENT_MAX_RETRIEVAL_CALLS, retrieval_reserve):
                append_error(state, "Knowledge retrieval call budget exhausted")
                break
            embedding_timeout = _bounded_timeout(
                state,
                RAG_EMBEDDING_TIMEOUT_SECONDS,
                retrieval_reserve,
                min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
            )
            if embedding_timeout < AGENT_MIN_CALL_TIMEOUT_SECONDS:
                append_error(state, "RAG retrieval skipped because the request deadline was nearly exhausted")
                break
            search_timeout = _bounded_timeout(
                state,
                RAG_EMBEDDING_TIMEOUT_SECONDS + QDRANT_SEARCH_RESERVE_SECONDS,
                AGENT_COMPOSER_RESERVE_SECONDS,
                min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
            )
            search_deadline = (
                min(deadline_monotonic, time.monotonic() + search_timeout)
                if deadline_monotonic is not None and search_timeout > 0
                else deadline_monotonic
            )
            started = time.monotonic()
            try:
                found = call_with_supported_kwargs(
                    search_fn,
                    query,
                    limit=5,
                    filters=filters,
                    use_rerank=False,
                    embedding_timeout=embedding_timeout,
                    timeout=search_timeout if search_timeout > 0 else embedding_timeout,
                    deadline_monotonic=search_deadline,
                )
                if degraded_observation(found):
                    raise ValueError("truncated retrieval result")
                for doc in found:
                    key = str(doc.get("doc_id") or doc.get("content") or doc.get("title") or "")
                    if key and key not in seen:
                        seen.add(key)
                        doc["retrieval_query"] = query
                        docs.append(doc)
                _trace_call(state, RAG_AGENT, "hybrid_search", started, "success",
                            source_version=next((doc.get("corpus_version") for doc in found
                                                 if doc.get("corpus_version")), None))
                break
            except Exception as exc:
                _trace_call(state, RAG_AGENT, "hybrid_search", started, "warning",
                            error_code=type(exc).__name__)
                logger.warning("Hybrid search failed (%s)", type(exc).__name__)
                backoff = _backoff_seconds(
                    state,
                    AGENT_RETRY_BACKOFF_SECONDS,
                    reserve_seconds=retrieval_reserve,
                    min_after_sleep=AGENT_MIN_CALL_TIMEOUT_SECONDS,
                )
                if (
                    attempt == 0
                    and not isinstance(exc, BudgetExhaustedError)
                    and _retryable_llm_error(exc)
                    and state.get("call_counts", {}).get("retrieval", 0) < AGENT_MAX_RETRIEVAL_CALLS
                    and backoff is not None
                    and _remaining_seconds(state) > AGENT_COMPOSER_RESERVE_SECONDS + 2
                ):
                    if backoff > 0:
                        time.sleep(backoff)
                    if not _is_cancelled(state):
                        append_trace(state, RAG_AGENT, "retry_transient_retrieval", "warning",
                                     "Retrying transient or truncated retrieval within budget.")
                        continue
                append_error(state, "Knowledge retrieval is temporarily unavailable")
                break
        if state.get("errors") and "Knowledge retrieval is temporarily unavailable" in state["errors"]:
            break

    try:
        started = time.monotonic()
        if docs and not _is_cancelled(state):
            rerank_timeout = _bounded_timeout(
                state,
                RERANK_TIMEOUT_SECONDS,
                AGENT_COMPOSER_RESERVE_SECONDS,
                min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
            )
            rerank_deadline = (
                min(deadline_monotonic, time.monotonic() + rerank_timeout)
                if deadline_monotonic is not None and rerank_timeout > 0
                else (time.monotonic() if rerank_timeout <= 0 else deadline_monotonic)
            )
            docs = call_with_supported_kwargs(
                rerank_fn,
                docs,
                question,
                top_n=5,
                timeout=rerank_timeout if rerank_timeout > 0 else 0.0,
                deadline_monotonic=rerank_deadline,
            )
            if docs:
                _trace_call(state, RAG_AGENT, "rerank", started, "success",
                            source_version=os.getenv("CORPUS_VERSION") or None)
        else:
            docs = docs[:5] if docs else []
    except Exception as exc:
        _trace_call(state, RAG_AGENT, "rerank", started, "warning",
                    error_code=type(exc).__name__)
        logger.warning("Rerank failed (%s)", type(exc).__name__)
        append_error(state, "Result reranking is temporarily unavailable")
        docs = docs[:5]

    state["retrieved_docs"] = docs
    _set_evidence_state(state, docs)
    append_trace(
        state,
        RAG_AGENT,
        "retrieve_health_context",
        "success" if docs else "warning",
        f"Retrieved {len(docs)} Health/InBody context documents.",
    )
    return state

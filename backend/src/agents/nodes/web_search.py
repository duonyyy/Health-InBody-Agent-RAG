"""Web Search Agent: retrieves recent health updates using Tavily."""

import logging
import time

from harness.budget import call_with_supported_kwargs
from harness.layers.injection_guard import clean_web_result
from integrations.tavily import tavily_search_health
from ..constants import (
    AGENT_COMPOSER_RESERVE_SECONDS,
    AGENT_MIN_CALL_TIMEOUT_SECONDS,
    WEB_SEARCH_AGENT,
    WEB_SEARCH_TIMEOUT_SECONDS,
)
from ..context import (
    _bounded_timeout,
    _count_call,
    _deadline_monotonic,
    _is_cancelled,
    _question,
    _trace_call,
)
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def web_search_agent(state: AgentState) -> AgentState:
    from .. import graph as graph_mod

    if WEB_SEARCH_AGENT not in state.get("selected_agents", []):
        return state

    tavily_fn = getattr(graph_mod, "tavily_search_health", tavily_search_health)

    question = _question(state)
    if _is_cancelled(state):
        append_error(state, "Web search skipped because request was cancelled")
        return state
    web_timeout = _bounded_timeout(
        state,
        WEB_SEARCH_TIMEOUT_SECONDS,
        reserve_seconds=AGENT_COMPOSER_RESERVE_SECONDS,
        min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
    )
    if web_timeout < AGENT_MIN_CALL_TIMEOUT_SECONDS:
        append_error(state, "Web search skipped because the request deadline was nearly exhausted")
        append_trace(
            state,
            WEB_SEARCH_AGENT,
            "web_search_budget_skipped",
            "warning",
            "Skipped web search to preserve composer deadline reserve.",
        )
        return state
    if not _count_call(state, "web", 1, reserve_seconds=AGENT_COMPOSER_RESERVE_SECONDS):
        append_error(state, "Web search call budget exhausted")
        return state
    started = time.monotonic()
    deadline_monotonic = _deadline_monotonic(state)
    web_deadline = (
        min(deadline_monotonic, started + web_timeout)
        if deadline_monotonic is not None
        else started + web_timeout
    )
    try:
        search_text = clean_web_result(
            call_with_supported_kwargs(
                tavily_fn,
                question,
                max_results=5,
                timeout=web_timeout,
                deadline_monotonic=web_deadline,
            )
        )
        if search_text is None:
            append_error(state, "Web result contained untrusted instructions")
            _trace_call(state, WEB_SEARCH_AGENT, "web_search", started, "warning",
                        error_code="UntrustedInstructions")
            return state
        if search_text.startswith("Lỗi tìm kiếm:"):
            append_error(state, "Web search is temporarily unavailable")
            _trace_call(state, WEB_SEARCH_AGENT, "web_search", started, "warning",
                        error_code="SearchError")
            append_trace(
                state,
                WEB_SEARCH_AGENT,
                "search_recent_health_web",
                "warning",
                "Web search returned an error; continuing without web context.",
            )
            return state
        results = list(state.get("tool_results") or [])
        results.append({"agent": WEB_SEARCH_AGENT, "tool": "tavily_search_health", "result": search_text})
        state["tool_results"] = results
        _trace_call(state, WEB_SEARCH_AGENT, "web_search", started, "success")
        append_trace(
            state,
            WEB_SEARCH_AGENT,
            "search_recent_health_web",
            "success",
            "Collected recent web context with Tavily.",
        )
    except Exception as exc:
        _trace_call(state, WEB_SEARCH_AGENT, "web_search", started, "warning",
                    error_code=type(exc).__name__)
        logger.warning("Web search failed (%s)", type(exc).__name__)
        append_error(state, "Web search is temporarily unavailable")
        append_trace(
            state,
            WEB_SEARCH_AGENT,
            "search_recent_health_web",
            "warning",
            "Web search failed; continuing without web context.",
        )
    return state

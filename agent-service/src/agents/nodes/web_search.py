"""Web Search Agent: retrieves recent health updates using Tavily."""

import logging
import time

from harness.layers.injection_guard import clean_web_result
from integrations.tavily import tavily_search_health
from ..constants import WEB_SEARCH_AGENT
from ..context import _count_call, _question, _trace_call
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def web_search_agent(state: AgentState) -> AgentState:
    from .. import graph as graph_mod

    if WEB_SEARCH_AGENT not in state.get("selected_agents", []):
        return state

    tavily_fn = getattr(graph_mod, "tavily_search_health", tavily_search_health)

    question = _question(state)
    if not _count_call(state, "web", 1):
        append_error(state, "Web search call budget exhausted")
        return state
    started = time.monotonic()
    try:
        search_text = clean_web_result(tavily_fn(question, max_results=5))
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

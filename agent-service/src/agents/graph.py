"""LangGraph-based Multi-Agent RAG Orchestrator for Health/InBody chat."""

import logging
import time
from typing import Any, Dict, List, Optional

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback keeps local dev usable without deps.
    END = "__end__"
    StateGraph = None

from health.tools import check_medical_safety
from integrations.tavily import tavily_search_health as _default_tavily_search_health
from llm.client import (
    openai_chat_complete as _default_openai_chat_complete,
    vietnamese_llm_chat_complete as _default_vietnamese_llm_chat_complete,
)
from memory import zep_memory
from memory.context import answer_memory_question
from memory.history import bounded_history
from rag.query_rewriter import (
    rewrite_query_to_multi_queries as _default_rewrite_query_to_multi_queries,
)
from rag.rerank import rerank_documents as _default_rerank_documents
from rag.search import hybrid_search as _default_hybrid_search

from .composer import (
    _build_evidence,
    _fallback_answer,
    _format_docs,
    _format_evidence,
    _safe_tool_results,
    _set_evidence_state,
    response_composer_agent,
)
from .constants import (
    AGENT_COMPOSER_RESERVE_SECONDS,
    AGENT_MAX_COMPOSER_CALLS,
    AGENT_MAX_RETRIEVAL_CALLS,
    AGENT_REQUEST_TIMEOUT_SECONDS,
    GENERAL_CHAT_AGENT,
    INBODY_AGENT,
    NUTRITION_AGENT,
    PERSONALIZATION_CONTEXT_AGENT,
    QDRANT_SEARCH_RESERVE_SECONDS,
    RAG_AGENT,
    RAG_COMPOSER_MAX_CHARS_PER_DOC,
    RAG_COMPOSER_MAX_DOCS,
    RAG_EMBEDDING_TIMEOUT_SECONDS,
    RAG_MAX_RETRIEVAL_QUERIES,
    RESPONSE_COMPOSER_AGENT,
    SAFETY_AGENT,
    SUPERVISOR_AGENT,
    TRAINING_AGENT,
    WEB_SEARCH_AGENT,
)
from .context import (
    _bounded_timeout,
    _count_call,
    _explicit_goal,
    _medical_conditions,
    _remaining_seconds,
    _trace_call,
)
from .fast_paths import (
    _apply_urgent_fast_path,
    _try_general_fast_path,
    _try_inbody_fast_path,
)
from .nodes import (
    _retrieval_filters,
    general_chat_agent,
    inbody_agent,
    normalize_question_agent,
    nutrition_agent,
    rag_agent,
    safety_agent,
    supervisor_agent,
    training_agent,
    web_search_agent,
)
from .state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)

# Re-exported dependencies for backward-compatibility with tests & patchers
openai_chat_complete = _default_openai_chat_complete
vietnamese_llm_chat_complete = _default_vietnamese_llm_chat_complete
rewrite_query_to_multi_queries = _default_rewrite_query_to_multi_queries
hybrid_search = _default_hybrid_search
rerank_documents = _default_rerank_documents
tavily_search_health = _default_tavily_search_health

_COMPILED_GRAPH = None


def _build_graph():
    if StateGraph is None:
        return None

    graph = StateGraph(AgentState)
    graph.add_node("normalize_question", normalize_question_agent)
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("inbody_agent", inbody_agent)
    graph.add_node("nutrition_agent", nutrition_agent)
    graph.add_node("training_agent", training_agent)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("web_search_agent", web_search_agent)
    graph.add_node("general_chat_agent", general_chat_agent)
    graph.add_node("safety_agent", safety_agent)
    graph.add_node("response_composer", response_composer_agent)

    graph.set_entry_point("normalize_question")
    graph.add_edge("normalize_question", "supervisor")
    graph.add_edge("supervisor", "inbody_agent")
    graph.add_edge("inbody_agent", "nutrition_agent")
    graph.add_edge("nutrition_agent", "training_agent")
    graph.add_edge("training_agent", "rag_agent")
    graph.add_edge("rag_agent", "web_search_agent")
    graph.add_edge("web_search_agent", "general_chat_agent")
    graph.add_edge("general_chat_agent", "safety_agent")
    graph.add_edge("safety_agent", "response_composer")
    graph.add_edge("response_composer", END)
    return graph.compile()


def _run_sequential(state: AgentState) -> AgentState:
    for node in [
        normalize_question_agent,
        supervisor_agent,
        inbody_agent,
        nutrition_agent,
        training_agent,
        rag_agent,
        web_search_agent,
        general_chat_agent,
        safety_agent,
        response_composer_agent,
    ]:
        state = node(state)
    return state


def _response_from_state(state: AgentState) -> Dict[str, Any]:
    errors = state.get("errors") or []
    return {
        "role": "assistant",
        "content": state.get("final_answer") or _fallback_answer(state),
        "status": "degraded" if errors else "ok",
        "fast_path": state.get("fast_path"),
        "agent_trace": state.get("agent_trace") or [],
        "selected_agents": state.get("selected_agents") or [],
        "tool_results": state.get("tool_results") or [],
        "retrieved_docs": state.get("retrieved_docs") or [],
        "evidence": state.get("evidence") or [],
        "claim_evidence_links": state.get("claim_evidence_links") or [],
        "evidence_status": state.get("evidence_status") or "not_required",
        "limitations": state.get("limitations") or [],
        "safety_result": state.get("safety_result") or {},
        "personalization_used": {
            "available": bool((state.get("personalization_context") or {}).get("available")),
            "reason": (state.get("personalization_context") or {}).get("reason"),
            "provenance": (state.get("personalization_context") or {}).get("provenance") or [],
        },
        "errors": errors,
    }


def multi_agent_handle(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[str] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    use_zep_memory: bool = False,
    conversation_id: str = "main",
) -> Dict[str, Any]:
    """Run the Health/InBody Multi-Agent RAG graph and return answer plus trace."""
    global _COMPILED_GRAPH
    personalization_context = user_profile or {}
    initial_state: AgentState = {
        "user_id": user_id,
        "question": question,
        "history": bounded_history(history or []),
        "user_profile": personalization_context,
        "personalization_context": personalization_context,
        "memory_context": "",
        "latest_measurement": personalization_context.get("latest_confirmed_measurement", {}),
        "tool_results": [],
        "retrieved_docs": [],
        "evidence": [],
        "claim_evidence_links": [],
        "evidence_status": "not_required",
        "limitations": [],
        "agent_trace": [],
        "errors": [],
        "deadline_monotonic": (
            time.monotonic() + AGENT_REQUEST_TIMEOUT_SECONDS
        ),
    }

    if not personalization_context.get("available") and personalization_context.get("reason"):
        append_trace(
            initial_state,
            PERSONALIZATION_CONTEXT_AGENT,
            "load_user_context",
            "warning",
            "Personalization context was unavailable; continued without saved profile data.",
        )
    elif personalization_context.get("available"):
        append_trace(
            initial_state,
            PERSONALIZATION_CONTEXT_AGENT,
            "load_user_context",
            "success",
            "Loaded saved user profile and/or latest InBody measurement.",
        )

    safety = check_medical_safety(question, _medical_conditions(initial_state))
    initial_state["safety_result"] = safety
    if safety.get("risk_level") == "urgent":
        return _response_from_state(_apply_urgent_fast_path(initial_state, safety))

    general_fast_path_state = _try_general_fast_path(initial_state)
    if general_fast_path_state is not None:
        return _response_from_state(general_fast_path_state)

    fast_path_state = _try_inbody_fast_path(initial_state)
    if fast_path_state is not None:
        return _response_from_state(fast_path_state)

    memory_answer = answer_memory_question(question, personalization_context)
    if memory_answer is not None and safety.get("risk_level") == "low":
        initial_state["final_answer"] = memory_answer
        initial_state["fast_path"] = "personal_memory"
        initial_state["selected_agents"] = ["PersonalMemoryAgent"]
        append_trace(initial_state, "PersonalMemoryAgent", "recall_confirmed_personal_data", "success",
                     "Read current owner-scoped records; no medical evidence was created.")
        return _response_from_state(initial_state)

    memory_allowed = bool(
        use_zep_memory and user_id and personalization_context.get("external_memory_consent")
        and safety.get("risk_level") == "low" and zep_memory.available()
    )
    if memory_allowed and _remaining_seconds(initial_state) > AGENT_COMPOSER_RESERVE_SECONDS + 3:
        started = time.monotonic()
        try:
            from memory import sync as memory_sync
            initial_state["memory_context"] = memory_sync.recall_confirmed(user_id, question)
            _trace_call(initial_state, "ZepMemory", "recall", started, "success")
        except Exception as exc:
            _trace_call(initial_state, "ZepMemory", "recall", started, "warning",
                        error_code=type(exc).__name__)

    try:
        if StateGraph is not None:
            if _COMPILED_GRAPH is None:
                _COMPILED_GRAPH = _build_graph()
            final_state = _COMPILED_GRAPH.invoke(initial_state)
        else:
            append_trace(
                initial_state,
                "LangGraphRuntime",
                "load_langgraph",
                "warning",
                "LangGraph is unavailable; used sequential fallback runner.",
            )
            final_state = _run_sequential(initial_state)
    except Exception as exc:
        logger.error("Multi-agent graph failed: %s", exc)
        append_error(initial_state, "Multi-agent processing is temporarily unavailable")
        append_trace(
            initial_state,
            "MultiAgentGraph",
            "run_graph",
            "error",
            "Graph failed; returned safe fallback answer.",
        )
        safety = check_medical_safety(question)
        initial_state["safety_result"] = safety
        initial_state["final_answer"] = _fallback_answer(initial_state)
        final_state = initial_state

    return _response_from_state(final_state)


def get_multi_agent_summary() -> Dict[str, Any]:
    return {
        "domain": "health_inbody",
        "orchestration": "LangGraph Multi-Agent RAG MVP",
        "entrypoint": "multi_agent_handle",
        "runtime_budget": {
            "request_timeout_seconds": AGENT_REQUEST_TIMEOUT_SECONDS,
            "composer_reserve_seconds": AGENT_COMPOSER_RESERVE_SECONDS,
            "rag_max_retrieval_queries": RAG_MAX_RETRIEVAL_QUERIES,
            "max_retrieval_calls": AGENT_MAX_RETRIEVAL_CALLS,
            "max_composer_calls": AGENT_MAX_COMPOSER_CALLS,
            "rag_embedding_timeout_seconds": RAG_EMBEDDING_TIMEOUT_SECONDS,
            "rag_composer_max_docs": RAG_COMPOSER_MAX_DOCS,
            "rag_composer_max_chars_per_doc": RAG_COMPOSER_MAX_CHARS_PER_DOC,
        },
        "agents": [
            {
                "name": PERSONALIZATION_CONTEXT_AGENT,
                "responsibility": "Load saved user profile and latest InBody measurement for personalization.",
            },
            {
                "name": SUPERVISOR_AGENT,
                "responsibility": "Select one or more specialist agents from the user question.",
            },
            {
                "name": INBODY_AGENT,
                "responsibility": "Calculate BMI and evaluate PBF/visceral fat from text metrics.",
            },
            {
                "name": RAG_AGENT,
                "responsibility": "Rewrite query, hybrid search Health/InBody corpus, rerank context.",
            },
            {
                "name": NUTRITION_AGENT,
                "responsibility": "Suggest protein range and calorie strategy.",
            },
            {
                "name": TRAINING_AGENT,
                "responsibility": "Suggest a basic weekly training plan.",
            },
            {
                "name": WEB_SEARCH_AGENT,
                "responsibility": "Search recent health web context when freshness is requested.",
            },
            {
                "name": SAFETY_AGENT,
                "responsibility": "Always run medical safety guardrail.",
            },
            {
                "name": RESPONSE_COMPOSER_AGENT,
                "responsibility": "Compose the final answer from agent outputs and safety context.",
            },
        ],
        "trace_schema": {
            "agent": "Agent name",
            "action": "Action performed",
            "status": "success | warning | error",
            "summary": "Short human-readable result",
        },
    }

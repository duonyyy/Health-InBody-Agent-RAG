"""Shared state and trace helpers for the Multi-Agent RAG MVP."""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_id: Optional[str]
    question: str
    history: List[Dict[str, str]]
    user_profile: Dict[str, Any]
    personalization_context: Dict[str, Any]
    latest_measurement: Dict[str, Any]
    standalone_question: str
    selected_agents: List[str]
    tool_results: List[Dict[str, Any]]
    retrieved_docs: List[Dict[str, Any]]
    safety_result: Dict[str, Any]
    agent_trace: List[Dict[str, str]]
    final_answer: str
    route: str
    errors: List[str]


def append_trace(
    state: AgentState,
    agent: str,
    action: str,
    status: str = "success",
    summary: Optional[str] = None,
) -> AgentState:
    trace = list(state.get("agent_trace") or [])
    trace.append(
        {
            "agent": agent,
            "action": action,
            "status": status,
            "summary": summary or "",
        }
    )
    state["agent_trace"] = trace
    return state


def append_error(state: AgentState, message: str) -> AgentState:
    errors = list(state.get("errors") or [])
    errors.append(message)
    state["errors"] = errors
    return state

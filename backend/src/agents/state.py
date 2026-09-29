"""Shared state and trace helpers for the Multi-Agent RAG MVP."""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_id: Optional[str]
    question: str
    history: List[Dict[str, str]]
    user_profile: Dict[str, Any]
    personalization_context: Dict[str, Any]
    memory_context: str
    latest_measurement: Dict[str, Any]
    standalone_question: str
    selected_agents: List[str]
    tool_results: List[Dict[str, Any]]
    retrieved_docs: List[Dict[str, Any]]
    composer_docs: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    claim_evidence_links: List[Dict[str, Any]]
    evidence_status: str
    limitations: List[str]
    safety_result: Dict[str, Any]
    agent_trace: List[Dict[str, Any]]
    call_counts: Dict[str, int]
    final_answer: str
    fast_path: str
    route: str
    errors: List[str]
    deadline_monotonic: float


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

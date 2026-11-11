"""Three graph specialists composed from existing deterministic capabilities."""

from .nodes import (
    general_chat_agent,
    inbody_agent,
    nutrition_agent,
    rag_agent,
    training_agent,
    web_search_agent,
)
from .state import AgentState


def _run_capabilities(state: AgentState, *steps) -> AgentState:
    # Existing capability implementations still inspect selected_agents. Restore
    # the public three-specialist contract before leaving this graph node.
    public_selection = list(state.get("selected_agents") or [])
    state["selected_agents"] = list(state.get("selected_capabilities") or [])
    try:
        for step in steps:
            state = step(state)
    finally:
        state["selected_agents"] = public_selection
    return state


def inbody_specialist(state: AgentState) -> AgentState:
    return _run_capabilities(state, inbody_agent)


def lifestyle_specialist(state: AgentState) -> AgentState:
    return _run_capabilities(state, nutrition_agent, training_agent)


def knowledge_specialist(state: AgentState) -> AgentState:
    return _run_capabilities(state, rag_agent, web_search_agent, general_chat_agent)

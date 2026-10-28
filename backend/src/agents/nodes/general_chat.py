"""General Chat Agent: passes through casual or greeting interactions."""

from ..constants import GENERAL_CHAT_AGENT
from ..state import AgentState, append_trace


def general_chat_agent(state: AgentState) -> AgentState:
    if GENERAL_CHAT_AGENT not in state.get("selected_agents", []):
        return state

    append_trace(
        state,
        GENERAL_CHAT_AGENT,
        "handle_general_chat",
        "success",
        "No specialized domain agent was required.",
    )
    return state

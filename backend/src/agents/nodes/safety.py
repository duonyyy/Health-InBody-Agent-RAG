"""Safety Agent: enforces deterministic medical safety checks."""

from health.tools import check_medical_safety
from ..constants import SAFETY_AGENT
from ..context import _medical_conditions, _question
from ..state import AgentState, append_trace


def safety_agent(state: AgentState) -> AgentState:
    safety = state.get("safety_result")
    if not safety:
        question = _question(state)
        safety = check_medical_safety(question, _medical_conditions(state))
    state["safety_result"] = safety
    append_trace(
        state,
        SAFETY_AGENT,
        "check_medical_safety",
        "success",
        f"Safety risk level: {safety.get('risk_level', 'unknown')}.",
    )
    return state

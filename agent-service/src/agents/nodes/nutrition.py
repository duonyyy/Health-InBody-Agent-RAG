"""Nutrition Agent: estimates protein and calorie strategies."""

from health.tools import suggest_nutrition_goal
from ..constants import NUTRITION_AGENT
from ..context import (
    _active_goal,
    _explicit_activity_level,
    _explicit_goal,
    _first_present,
    _latest_measurement,
    _profile,
    _question,
)
from ..parsing import extract_weight_kg
from ..state import AgentState, append_trace


def nutrition_agent(state: AgentState) -> AgentState:
    if NUTRITION_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    profile = _profile(state)
    latest = _latest_measurement(state)
    active_goal = _active_goal(state)
    weight = _first_present(extract_weight_kg(question), latest.get("weight_kg"))
    goal = _first_present(
        _explicit_goal(question),
        active_goal.get("goal_type"),
        profile.get("goal"),
    )
    activity_level = _first_present(
        _explicit_activity_level(question),
        active_goal.get("weekly_activity_level"),
        profile.get("activity_level"),
    )
    missing = [
        label
        for value, label in (
            (weight, "cân nặng hiện tại đã xác nhận"),
            (goal, "mục tiêu"),
            (activity_level, "mức vận động"),
        )
        if value is None
    ]
    if missing:
        result = {
            "need_more_info": True,
            "missing_fields": missing,
            "message": "Cần thêm " + ", ".join(missing) + " để lập gợi ý dinh dưỡng mà không đoán dữ liệu.",
        }
    else:
        result = suggest_nutrition_goal(goal, weight, activity_level)
    results = list(state.get("tool_results") or [])
    results.append({"agent": NUTRITION_AGENT, "tool": "suggest_nutrition_goal", "result": result})
    state["tool_results"] = results
    append_trace(
        state,
        NUTRITION_AGENT,
        "suggest_nutrition_goal",
        "warning" if missing else "success",
        "Requested missing confirmed nutrition inputs."
        if missing
        else f"Estimated nutrition strategy for {goal} using confirmed/explicit inputs.",
    )
    return state

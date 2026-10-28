"""Training Agent: constructs personalized weekly exercise plans."""

from health.tools import suggest_training_plan
from ..constants import TRAINING_AGENT
from ..context import (
    _active_goal,
    _explicit_fitness_level,
    _explicit_goal,
    _first_present,
    _profile,
    _question,
)
from ..parsing import infer_days_per_week
from ..state import AgentState, append_trace


def training_agent(state: AgentState) -> AgentState:
    if TRAINING_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    profile = _profile(state)
    active_goal = _active_goal(state)
    goal = _first_present(
        _explicit_goal(question),
        active_goal.get("goal_type"),
        profile.get("goal"),
    )
    days = _first_present(
        infer_days_per_week(question),
        active_goal.get("training_days_per_week"),
    )
    fitness_level = _explicit_fitness_level(question)
    missing = [
        label
        for value, label in (
            (goal, "mục tiêu"),
            (days, "số buổi mỗi tuần"),
            (fitness_level, "trình độ tập luyện"),
        )
        if value is None
    ]
    if missing:
        result = {
            "need_more_info": True,
            "missing_fields": missing,
            "message": "Cần thêm " + ", ".join(missing) + " để lập lịch tập mà không đoán dữ liệu.",
        }
    else:
        result = suggest_training_plan(
            goal,
            fitness_level=fitness_level,
            days_per_week=days,
        )
    results = list(state.get("tool_results") or [])
    results.append({"agent": TRAINING_AGENT, "tool": "suggest_training_plan", "result": result})
    state["tool_results"] = results
    append_trace(
        state,
        TRAINING_AGENT,
        "suggest_training_plan",
        "warning" if missing else "success",
        "Requested missing confirmed training inputs."
        if missing
        else f"Built a {days}-day weekly training plan for {goal}.",
    )
    return state

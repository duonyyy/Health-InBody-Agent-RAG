"""Context extraction, time budgeting, and state helper functions."""

import json
import re
import time
from typing import Any, Dict, List, Optional

from harness.layers.budget_policy import reserve_allows_call
from .constants import AGENT_REQUEST_TIMEOUT_SECONDS
from .parsing import infer_goal, normalize_match_text
from .state import AgentState, append_trace


def _count_call(
    state: AgentState, name: str, maximum: int, reserve_seconds: float = 0.0
) -> bool:
    counts = dict(state.get("call_counts") or {})
    if not reserve_allows_call(
        remaining_seconds=_remaining_seconds(state),
        reserve_seconds=reserve_seconds,
        used=counts.get(name, 0),
        maximum=maximum,
    ):
        append_trace(
            state, name, "call_budget_exhausted", "warning", "Route call budget reached."
        )
        return False
    counts[name] = counts.get(name, 0) + 1
    state["call_counts"] = counts
    return True


def _trace_call(
    state: AgentState,
    agent: str,
    action: str,
    started: float,
    status: str,
    error_code: Optional[str] = None,
    source_version: Optional[str] = None,
) -> None:
    append_trace(
        state, agent, action, status, "External call completed without logging health input."
    )
    state["agent_trace"][-1].update(
        {
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "error_code": error_code,
            "source_version": source_version,
        }
    )


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _question(state: AgentState) -> str:
    return state.get("standalone_question") or state.get("question") or ""


def _remaining_seconds(state: AgentState) -> float:
    deadline = state.get("deadline_monotonic")
    if deadline is None:
        return AGENT_REQUEST_TIMEOUT_SECONDS
    return max(0.0, float(deadline) - time.monotonic())


def _bounded_timeout(
    state: AgentState,
    configured_timeout: float,
    reserve_seconds: float = 0.0,
) -> float:
    return max(
        0.0,
        min(
            float(configured_timeout),
            _remaining_seconds(state) - float(reserve_seconds),
        ),
    )


def _personalization_context(state: AgentState) -> Dict[str, Any]:
    return state.get("personalization_context") or state.get("user_profile") or {}


def _profile(state: AgentState) -> Dict[str, Any]:
    return _personalization_context(state).get("profile") or {}


def _latest_measurement(state: AgentState) -> Dict[str, Any]:
    return (
        state.get("latest_measurement")
        or _personalization_context(state).get("latest_confirmed_measurement")
        or _personalization_context(state).get("latest_measurement")
        or {}
    )


def _active_goal(state: AgentState) -> Dict[str, Any]:
    return _personalization_context(state).get("active_goal") or {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _medical_conditions(state: AgentState) -> List[str]:
    conditions = _profile(state).get("medical_conditions")
    if not conditions:
        return []
    if isinstance(conditions, list):
        return [str(item) for item in conditions if str(item).strip()]
    return [item.strip() for item in str(conditions).split(",") if item.strip()]


def _explicit_goal(question: str) -> Optional[str]:
    return infer_goal(question)


def _ensure_agent(state: AgentState, agent_name: str) -> None:
    selected = list(state.get("selected_agents") or [])
    if agent_name not in selected:
        selected.append(agent_name)
    state["selected_agents"] = selected


def _has_any(text: str, keywords: List[str]) -> bool:
    norm_text = f" {normalize_match_text(text)} "
    for keyword in keywords:
        norm_kw = normalize_match_text(keyword)
        pattern = r"(?<!\w)" + re.escape(norm_kw) + r"(?!\w)"
        if re.search(pattern, norm_text):
            return True
    return False


def _explicit_activity_level(question: str) -> Optional[str]:
    text = normalize_match_text(question)
    if any(value in text for value in ["rat nang", "very high", "very_high"]):
        return "very_high"
    if any(value in text for value in ["hoat dong cao", "van dong cao", "high activity"]):
        return "high"
    if any(value in text for value in ["hoat dong vua", "van dong vua", "moderate"]):
        return "moderate"
    if any(
        value in text
        for value in [
            "it van dong",
            "hoat dong thap",
            "sedentary",
            "low activity",
            "ngoi nhieu",
            "dan van phong",
            "khong tap the duc",
            "it di lai",
        ]
    ):
        return "low"
    return None


def _explicit_fitness_level(question: str) -> Optional[str]:
    text = normalize_match_text(question)
    if any(
        value in text
        for value in [
            "moi tap",
            "beginner",
            "nguoi moi",
            "moi bat dau",
            "chua tung tap",
            "moi di gym",
            "nguoi moi bat dau",
        ]
    ):
        return "beginner"
    if any(value in text for value in ["trung cap", "intermediate"]):
        return "intermediate"
    if any(value in text for value in ["nang cao", "advanced"]):
        return "advanced"
    return None

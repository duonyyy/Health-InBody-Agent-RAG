"""Supervisor Agent: intent detection and routing to specialist agents."""

import logging
from typing import List

from harness.budget import call_with_supported_kwargs
from llm.client import (
    AGENT_TOOLS_ROUTE,
    GENERAL_CHAT_ROUTE,
    HEALTH_RAG_ROUTE,
    LLM_ROUTER_TIMEOUT,
    WEB_SEARCH_ROUTE,
    _keyword_route,
    detect_route,
)
from ..constants import (
    AGENT_COMPOSER_RESERVE_SECONDS,
    AGENT_MIN_CALL_TIMEOUT_SECONDS,
    GENERAL_CHAT_AGENT,
    INBODY_AGENT,
    NUTRITION_AGENT,
    RAG_AGENT,
    SAFETY_AGENT,
    SUPERVISOR_AGENT,
    TRAINING_AGENT,
    WEB_SEARCH_AGENT,
    public_specialists,
)
from ..context import (
    _bounded_timeout,
    _deadline_monotonic,
    _has_any,
    _is_cancelled,
    _question,
)
from ..parsing import (
    extract_height_cm,
    extract_pbf,
    extract_visceral_fat,
    extract_weight_kg,
    normalize_match_text,
)
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def _select_agents(state: AgentState, capabilities: List[str]) -> AgentState:
    state["selected_capabilities"] = list(dict.fromkeys(capabilities))
    state["selected_agents"] = public_specialists(state["selected_capabilities"])
    append_trace(
        state, SUPERVISOR_AGENT, "select_agents", "success",
        "Selected specialists: {}".format(", ".join(state["selected_agents"])),
    )
    return state


def supervisor_agent(state: AgentState) -> AgentState:
    if (state.get("safety_result") or {}).get("risk_level") == "medical_caution":
        # Restrict before any fallback route classifier can call a provider.
        append_trace(
            state, SAFETY_AGENT, "restrict_medical_caution_route", "warning",
            "Restricted routing to medical-safety retrieval; skipped plan and web agents.",
        )
        return _select_agents(state, [RAG_AGENT])
    question = _question(state)
    text = normalize_match_text(question)
    selected: List[str] = []

    def _safe_extract(fn):
        try:
            return fn(question)
        except Exception:
            return None

    has_metrics = any(
        value is not None
        for value in [
            _safe_extract(extract_weight_kg),
            _safe_extract(extract_height_cm),
            _safe_extract(extract_pbf),
            _safe_extract(extract_visceral_fat),
        ]
    )
    if has_metrics or _has_any(text, ["bmi", "pbf", "smm", "bfm", "mỡ nội tạng", "visceral"]):
        selected.append(INBODY_AGENT)

    if _has_any(
        text,
        [
            "protein",
            "calo",
            "calorie",
            "dinh dưỡng",
            "ăn",
            "khẩu phần",
            "thực đơn",
            "chế độ ăn",
            "bữa ăn",
            "uống whey",
            "carb",
            "tinh bột",
            "chất béo",
        ],
    ):
        selected.append(NUTRITION_AGENT)

    if _has_any(
        text,
        [
            "lịch tập",
            "tập luyện",
            "cardio",
            "kháng lực",
            "buổi/tuần",
            "buổi mỗi tuần",
            "tập gym",
            "tập tạ",
            "bài tập",
            "giáo án tập",
            "chạy bộ",
        ],
    ):
        selected.append(TRAINING_AGENT)

    if _has_any(text, ["mới nhất", "gần đây", "hôm nay", "năm 2026", "vừa công bố"]):
        selected.append(WEB_SEARCH_AGENT)

    if _has_any(
        text,
        [
            "inbody",
            "bmi",
            "pbf",
            "smm",
            "bfm",
            "giảm mỡ",
            "tăng cơ",
            "mỡ nội tạng",
            "dinh dưỡng",
            "tập luyện",
            "giải thích",
            "ý nghĩa",
            "khác nhau",
            "là gì",
            "tại sao",
            "nguyên nhân",
            "tác dụng",
            "tác hại",
            "nguy hiểm không",
            "bổ sung",
            "uống",
        ],
    ):
        selected.append(RAG_AGENT)

    if not selected:
        router_timeout = _bounded_timeout(
            state,
            LLM_ROUTER_TIMEOUT,
            reserve_seconds=AGENT_COMPOSER_RESERVE_SECONDS,
            min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
        )
        if _is_cancelled(state) or router_timeout <= 0:
            route = _keyword_route(question)
            append_trace(
                state,
                SUPERVISOR_AGENT,
                "route_budget_fallback",
                "warning",
                "Used deterministic keyword route because request budget was low.",
            )
        else:
            try:
                route = call_with_supported_kwargs(
                    detect_route,
                    state.get("history") or [],
                    question,
                    timeout=router_timeout,
                    deadline_monotonic=_deadline_monotonic(state),
                )
            except Exception as exc:
                logger.warning("Route detection failed: %s", exc)
                route = GENERAL_CHAT_ROUTE
                append_error(state, "Route detection is temporarily unavailable")
        state["route"] = route
        if route == HEALTH_RAG_ROUTE:
            selected.append(RAG_AGENT)
        elif route == AGENT_TOOLS_ROUTE:
            selected.append(INBODY_AGENT)
        elif route == WEB_SEARCH_ROUTE:
            selected.append(WEB_SEARCH_AGENT)
        else:
            selected.append(GENERAL_CHAT_AGENT)

    return _select_agents(state, selected)

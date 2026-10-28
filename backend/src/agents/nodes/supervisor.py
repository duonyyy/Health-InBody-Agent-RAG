"""Supervisor Agent: intent detection and routing to specialist agents."""

import logging
from typing import List

from llm.client import (
    AGENT_TOOLS_ROUTE,
    GENERAL_CHAT_ROUTE,
    HEALTH_RAG_ROUTE,
    WEB_SEARCH_ROUTE,
    detect_route,
)
from ..constants import (
    GENERAL_CHAT_AGENT,
    INBODY_AGENT,
    NUTRITION_AGENT,
    RAG_AGENT,
    SAFETY_AGENT,
    SUPERVISOR_AGENT,
    TRAINING_AGENT,
    WEB_SEARCH_AGENT,
)
from ..context import _has_any, _question
from ..parsing import (
    extract_height_cm,
    extract_pbf,
    extract_visceral_fat,
    extract_weight_kg,
    normalize_match_text,
)
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def supervisor_agent(state: AgentState) -> AgentState:
    question = _question(state)
    text = normalize_match_text(question)
    selected: List[str] = []

    has_metrics = any(
        value is not None
        for value in [
            extract_weight_kg(question),
            extract_height_cm(question),
            extract_pbf(question),
            extract_visceral_fat(question),
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
        try:
            route = detect_route(state.get("history") or [], question)
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

    deduped = []
    for agent_name in selected:
        if agent_name not in deduped:
            deduped.append(agent_name)

    if (state.get("safety_result") or {}).get("risk_level") == "medical_caution":
        # A symptom, medication or known condition must not be turned into an
        # automated nutrition/training plan. Retrieve only safety context; the
        # SafetyAgent and composer will preserve the cautionary response.
        deduped = [RAG_AGENT]
        append_trace(
            state,
            SAFETY_AGENT,
            "restrict_medical_caution_route",
            "warning",
            "Restricted routing to medical-safety retrieval; skipped plan and web agents.",
        )
    state["selected_agents"] = deduped
    append_trace(
        state,
        SUPERVISOR_AGENT,
        "select_agents",
        "success",
        "Selected agents: {}".format(", ".join(deduped)),
    )
    return state

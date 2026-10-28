"""InBody Agent: metric extraction and health classification."""

from health.tools import (
    calculate_bmi,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
)
from ..constants import INBODY_AGENT
from ..context import (
    _first_present,
    _latest_measurement,
    _profile,
    _question,
)
from ..parsing import (
    extract_height_cm,
    extract_pbf,
    extract_sex,
    extract_visceral_fat,
    extract_weight_kg,
)
from ..state import AgentState, append_trace


def inbody_agent(state: AgentState) -> AgentState:
    if INBODY_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    text = question.lower()
    results = list(state.get("tool_results") or [])
    added = []

    profile = _profile(state)
    latest = _latest_measurement(state)

    weight = _first_present(
        extract_weight_kg(question),
        latest.get("weight_kg"),
    )
    height = _first_present(
        extract_height_cm(question),
        latest.get("height_cm"),
        profile.get("height_cm"),
    )
    if weight and height:
        result = calculate_bmi(weight, height)
        results.append({"agent": INBODY_AGENT, "tool": "calculate_bmi", "result": result})
        added.append("BMI")
    elif "bmi" in text:
        results.append(
            {
                "agent": INBODY_AGENT,
                "tool": "calculate_bmi",
                "result": {
                    "need_more_info": True,
                    "message": "Cần cân nặng (kg) và chiều cao (cm) để tính BMI chính xác.",
                },
            }
        )
        added.append("BMI needs more info")

    pbf = _first_present(extract_pbf(question), latest.get("pbf_percent"))
    if pbf is not None:
        result = evaluate_body_fat_percentage(
            pbf,
            _first_present(extract_sex(question), profile.get("sex")),
        )
        results.append({"agent": INBODY_AGENT, "tool": "evaluate_body_fat_percentage", "result": result})
        added.append("PBF")
    elif "pbf" in text or "phần trăm mỡ" in text:
        results.append(
            {
                "agent": INBODY_AGENT,
                "tool": "evaluate_body_fat_percentage",
                "result": {
                    "need_more_info": True,
                    "message": "Cần giá trị PBF (%) và tốt nhất có thêm giới tính/tuổi.",
                },
            }
        )
        added.append("PBF needs more info")

    visceral_fat = _first_present(
        extract_visceral_fat(question),
        latest.get("visceral_fat_level"),
    )
    if visceral_fat is not None:
        result = evaluate_visceral_fat(visceral_fat)
        results.append({"agent": INBODY_AGENT, "tool": "evaluate_visceral_fat", "result": result})
        added.append("visceral fat")
    elif "mỡ nội tạng" in text or "visceral" in text:
        results.append(
            {
                "agent": INBODY_AGENT,
                "tool": "evaluate_visceral_fat",
                "result": {
                    "need_more_info": True,
                    "message": "Cần visceral fat level/mức mỡ nội tạng trên báo cáo InBody.",
                },
            }
        )
        added.append("visceral fat needs more info")

    state["tool_results"] = results
    append_trace(
        state,
        INBODY_AGENT,
        "evaluate_inbody_metrics",
        "success",
        "Evaluated {}.".format(", ".join(added) if added else "no explicit metric values"),
    )
    return state

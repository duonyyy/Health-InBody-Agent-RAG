"""Deterministic fast-paths for urgent safety, greetings, and direct InBody calculations."""

from typing import Any, Dict, List, Optional

from health.tools import (
    calculate_bmi,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
)
from .constants import (
    GENERAL_CHAT_AGENT,
    INBODY_AGENT,
    RESPONSE_COMPOSER_AGENT,
    SAFETY_AGENT,
)
from .context import (
    _first_present,
    _has_any,
    _latest_measurement,
    _profile,
    _question,
)
from .parsing import (
    extract_height_cm,
    extract_pbf,
    extract_sex,
    extract_visceral_fat,
    extract_weight_kg,
    normalize_match_text,
)
from .state import AgentState, append_trace


def _urgent_answer() -> str:
    return (
        "Các dấu hiệu bạn mô tả có thể cần được đánh giá y tế khẩn cấp. "
        "Hãy dừng tập ngay, nghỉ ở nơi an toàn và liên hệ cơ sở cấp cứu/y tế gần nhất. "
        "Nếu triệu chứng đang tiếp diễn, nặng lên hoặc bạn ở một mình, hãy nhờ người khác hỗ trợ; "
        "không tự tiếp tục tập hoặc tự lái xe khi đang choáng, đau ngực hay khó thở. "
        "Thông tin này chỉ nhằm cảnh báo an toàn, không phải chẩn đoán."
    )


def _apply_urgent_fast_path(state: AgentState, safety: Dict[str, Any]) -> AgentState:
    state["selected_agents"] = [SAFETY_AGENT]
    state["safety_result"] = safety
    state["final_answer"] = _urgent_answer()
    state["fast_path"] = "urgent_safety"
    state["evidence"] = []
    state["evidence_status"] = "not_required"
    state["limitations"] = [
        "Đây là cảnh báo an toàn khẩn cấp, không phải chẩn đoán y khoa."
    ]
    append_trace(
        state,
        SAFETY_AGENT,
        "urgent_safety_fast_path",
        "success",
        "Returned deterministic urgent guidance without LLM or retrieval.",
    )
    return state


def _try_general_fast_path(state: AgentState) -> Optional[AgentState]:
    question = _question(state)
    text = normalize_match_text(question)
    greeting_patterns = [
        "xin chao",
        "chao ban",
        "hello",
        "hi",
        "cam on",
        "ban la ai",
        "ban giup duoc gi",
        "co the giup gi",
    ]
    if not any(
        re_pattern in f" {text} "
        if len(re_pattern) > 2
        else f" {re_pattern} " in f" {text} "
        for re_pattern in greeting_patterns
    ):
        return None

    state["selected_agents"] = [GENERAL_CHAT_AGENT]
    state["final_answer"] = (
        "Xin chào! Mình có thể giúp bạn tính và giải thích BMI, PBF, mỡ nội tạng, "
        "tham khảo mục tiêu dinh dưỡng và xây lịch tập cơ bản. "
        "Bạn có thể nhập trực tiếp các chỉ số, ví dụ: “Tôi nặng 72 kg, cao 170 cm, "
        "BMI của tôi là bao nhiêu?”. Thông tin chỉ mang tính tham khảo và không thay thế bác sĩ."
    )
    state["fast_path"] = "general_chat"
    state["evidence"] = []
    state["evidence_status"] = "not_required"
    state["limitations"] = []
    append_trace(
        state,
        SAFETY_AGENT,
        "precheck_medical_safety",
        "success",
        "Safety risk level: low.",
    )
    append_trace(
        state,
        GENERAL_CHAT_AGENT,
        "general_chat_fast_path",
        "success",
        "Returned deterministic greeting and capability summary.",
    )
    append_trace(
        state,
        RESPONSE_COMPOSER_AGENT,
        "compose_template_answer",
        "success",
        "Rendered a deterministic Vietnamese greeting.",
    )
    return state


def _try_inbody_fast_path(state: AgentState) -> Optional[AgentState]:
    """Return deterministic InBody calculations when no broader advice is requested."""
    question = _question(state)
    text = normalize_match_text(question)
    if _has_any(
        text,
        [
            "protein",
            "calo",
            "dinh duong",
            "an uong",
            "khau phan",
            "lich tap",
            "tap luyen",
            "cardio",
            "khang luc",
            "giam mo",
            "tang co",
            "thuc don",
        ],
    ):
        return None

    latest = _latest_measurement(state)
    profile = _profile(state)
    results: List[Dict[str, Any]] = []
    answer_lines: List[str] = []

    weight = _first_present(extract_weight_kg(question), latest.get("weight_kg"))
    height = _first_present(
        extract_height_cm(question),
        latest.get("height_cm"),
        profile.get("height_cm"),
    )
    if "bmi" in text and weight and height:
        result = calculate_bmi(weight, height)
        if not result.get("error"):
            labels = {
                "underweight": "thiếu cân",
                "normal": "trong ngưỡng tham khảo",
                "overweight_risk": "tiền thừa cân theo ngưỡng châu Á",
                "overweight": "thừa cân",
                "obesity": "béo phì",
            }
            results.append(
                {"agent": INBODY_AGENT, "tool": "calculate_bmi", "result": result}
            )
            answer_lines.append(
                f"- BMI của bạn là **{result['bmi']:.2f}**, thuộc nhóm "
                f"**{labels.get(result['category'], result['category'])}**."
            )

    pbf = _first_present(extract_pbf(question), latest.get("pbf_percent"))
    if pbf is not None and _has_any(text, ["pbf", "phan tram mo", "mo co the"]):
        result = evaluate_body_fat_percentage(
            pbf,
            _first_present(
                extract_sex(question),
                profile.get("sex_at_birth"),
                profile.get("sex"),
            ),
        )
        if not result.get("error"):
            labels = {
                "low": "thấp",
                "normal": "trong ngưỡng tham khảo",
                "high": "cao",
                "very_high": "rất cao",
            }
            results.append(
                {
                    "agent": INBODY_AGENT,
                    "tool": "evaluate_body_fat_percentage",
                    "result": result,
                }
            )
            answer_lines.append(
                f"- PBF **{result['pbf_percent']}%** được phân loại **"
                f"{labels.get(result['category'], result['category'])}** "
                f"theo giới tính `{result['sex']}`."
            )

    visceral_fat = _first_present(
        extract_visceral_fat(question),
        latest.get("visceral_fat_level"),
    )
    if visceral_fat is not None and _has_any(text, ["mo noi tang", "visceral"]):
        result = evaluate_visceral_fat(visceral_fat)
        if not result.get("error"):
            labels = {
                "normal": "trong ngưỡng tham khảo",
                "elevated": "hơi cao",
                "high": "cao",
            }
            results.append(
                {
                    "agent": INBODY_AGENT,
                    "tool": "evaluate_visceral_fat",
                    "result": result,
                }
            )
            answer_lines.append(
                f"- Mỡ nội tạng level **{result['visceral_fat_level']}** được đánh giá "
                f"**{labels.get(result['risk'], result['risk'])}**."
            )

    if not results:
        return None

    answer_lines.append(
        "\nCác chỉ số trên chỉ dùng để sàng lọc/tham khảo; nên đọc cùng thành phần cơ thể, "
        "tiền sử sức khỏe và triệu chứng thực tế."
    )
    append_trace(
        state,
        SAFETY_AGENT,
        "precheck_medical_safety",
        "success",
        "Safety risk level: low.",
    )
    state["selected_agents"] = [INBODY_AGENT]
    state["tool_results"] = results
    state["final_answer"] = "\n".join(answer_lines)
    state["fast_path"] = "inbody_tools"
    state["evidence"] = []
    state["evidence_status"] = "not_required"
    state["limitations"] = [
        "Kết quả là phép tính sàng lọc; cần đọc cùng PBF, SMM, triệu chứng và tiền sử sức khỏe."
    ]
    append_trace(
        state,
        INBODY_AGENT,
        "deterministic_inbody_fast_path",
        "success",
        "Returned explicit InBody calculations without LLM or retrieval.",
    )
    append_trace(
        state,
        RESPONSE_COMPOSER_AGENT,
        "compose_template_answer",
        "success",
        "Rendered a deterministic Vietnamese answer from tool results.",
    )
    return state

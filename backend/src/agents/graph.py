"""LangGraph-based Multi-Agent RAG MVP for Health/InBody chat."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback keeps local dev usable without deps.
    END = "__end__"
    StateGraph = None

from llm.client import (
    AGENT_TOOLS_ROUTE,
    GENERAL_CHAT_ROUTE,
    HEALTH_RAG_ROUTE,
    LLM_COMPOSER_MAX_TOKENS,
    LLM_COMPOSER_TIMEOUT,
    WEB_SEARCH_ROUTE,
    detect_route,
    detect_user_intent,
    openai_chat_complete,
    vietnamese_llm_chat_complete,
)
from health.tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from rag.query_rewriter import rewrite_query_to_multi_queries
from rag.rerank import rerank_documents
from rag.search import hybrid_search
from integrations.tavily import tavily_search_health

from .parsing import (
    extract_height_cm,
    extract_pbf,
    extract_sex,
    extract_visceral_fat,
    extract_weight_kg,
    infer_days_per_week,
    infer_goal,
    normalize_match_text,
)
from .state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)

INBODY_AGENT = "InBodyAgent"
RAG_AGENT = "RAGAgent"
NUTRITION_AGENT = "NutritionAgent"
TRAINING_AGENT = "TrainingAgent"
WEB_SEARCH_AGENT = "WebSearchAgent"
GENERAL_CHAT_AGENT = "GeneralChatAgent"
SAFETY_AGENT = "SafetyAgent"
RESPONSE_COMPOSER_AGENT = "ResponseComposerAgent"
SUPERVISOR_AGENT = "SupervisorAgent"
PERSONALIZATION_CONTEXT_AGENT = "PersonalizationContextAgent"

AGENT_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30")
)
AGENT_COMPOSER_RESERVE_SECONDS = float(
    os.getenv("AGENT_COMPOSER_RESERVE_SECONDS", "10")
)
RAG_EMBEDDING_TIMEOUT_SECONDS = float(
    os.getenv("RAG_EMBEDDING_TIMEOUT_SECONDS", "10")
)
QDRANT_SEARCH_RESERVE_SECONDS = float(
    os.getenv("QDRANT_SEARCH_RESERVE_SECONDS", "5")
)
RAG_MAX_RETRIEVAL_QUERIES = max(
    1,
    int(os.getenv("RAG_MAX_RETRIEVAL_QUERIES", "1")),
)
RAG_COMPOSER_MAX_DOCS = max(
    1,
    int(os.getenv("RAG_COMPOSER_MAX_DOCS", "3")),
)
RAG_COMPOSER_MAX_CHARS_PER_DOC = max(
    200,
    int(os.getenv("RAG_COMPOSER_MAX_CHARS_PER_DOC", "700")),
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
        or _personalization_context(state).get("latest_measurement")
        or {}
    )


def _first_present(*values):
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
    text = normalize_match_text(question)
    if "tang co" in text or "muscle" in text:
        return "muscle_gain"
    if "duy tri" in text or "maintenance" in text:
        return "maintenance"
    if "giam mo" in text or "fat loss" in text or "fat_loss" in text:
        return "fat_loss"
    return None


def _ensure_agent(state: AgentState, agent_name: str) -> None:
    selected = list(state.get("selected_agents") or [])
    if agent_name not in selected:
        selected.append(agent_name)
    state["selected_agents"] = selected


def _has_any(text: str, keywords: List[str]) -> bool:
    normalized_text = normalize_match_text(text)
    return any(normalize_match_text(keyword) in normalized_text for keyword in keywords)


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
            _first_present(extract_sex(question), profile.get("sex")),
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


def normalize_question_agent(state: AgentState) -> AgentState:
    question = state.get("question") or ""
    history = state.get("history") or []
    try:
        standalone = detect_user_intent(history, question)
        state["standalone_question"] = standalone or question
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_follow_up_question",
            "success",
            "Prepared standalone question from conversation history.",
        )
    except Exception as exc:
        logger.warning("Question normalization failed: %s", exc)
        state["standalone_question"] = question
        append_error(state, f"Question normalization failed: {exc}")
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_follow_up_question",
            "warning",
            "Used original question because normalization failed.",
        )
    return state


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

    if _has_any(text, ["protein", "calo", "calorie", "dinh dưỡng", "ăn", "khẩu phần"]):
        selected.append(NUTRITION_AGENT)

    if _has_any(text, ["lịch tập", "tập luyện", "cardio", "kháng lực", "buổi/tuần", "buổi mỗi tuần"]):
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
        ],
    ):
        selected.append(RAG_AGENT)

    if not selected:
        try:
            route = detect_route(state.get("history") or [], question)
        except Exception as exc:
            logger.warning("Route detection failed: %s", exc)
            route = GENERAL_CHAT_ROUTE
            append_error(state, f"Route detection failed: {exc}")
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
    state["selected_agents"] = deduped
    append_trace(
        state,
        SUPERVISOR_AGENT,
        "select_agents",
        "success",
        "Selected agents: {}".format(", ".join(deduped)),
    )
    return state


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


def nutrition_agent(state: AgentState) -> AgentState:
    if NUTRITION_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    profile = _profile(state)
    latest = _latest_measurement(state)
    weight = _first_present(extract_weight_kg(question), latest.get("weight_kg")) or 70
    goal = _first_present(_explicit_goal(question), latest.get("recommendation_goal"), profile.get("goal")) or infer_goal(question)
    activity_level = profile.get("activity_level") or "moderate"
    result = suggest_nutrition_goal(goal, weight, activity_level)
    results = list(state.get("tool_results") or [])
    results.append({"agent": NUTRITION_AGENT, "tool": "suggest_nutrition_goal", "result": result})
    state["tool_results"] = results
    append_trace(
        state,
        NUTRITION_AGENT,
        "suggest_nutrition_goal",
        "success",
        f"Estimated nutrition strategy for {goal} using weight {weight}kg.",
    )
    return state


def training_agent(state: AgentState) -> AgentState:
    if TRAINING_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    profile = _profile(state)
    latest = _latest_measurement(state)
    goal = _first_present(_explicit_goal(question), latest.get("recommendation_goal"), profile.get("goal")) or infer_goal(question)
    days = infer_days_per_week(question)
    result = suggest_training_plan(goal, fitness_level="beginner", days_per_week=days)
    results = list(state.get("tool_results") or [])
    results.append({"agent": TRAINING_AGENT, "tool": "suggest_training_plan", "result": result})
    state["tool_results"] = results
    append_trace(
        state,
        TRAINING_AGENT,
        "suggest_training_plan",
        "success",
        f"Built a {days}-day weekly training plan for {goal}.",
    )
    return state


def rag_agent(state: AgentState) -> AgentState:
    if RAG_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    queries = [question]
    if RAG_MAX_RETRIEVAL_QUERIES > 1:
        rewrite_timeout = _bounded_timeout(
            state,
            LLM_REWRITE_TIMEOUT,
            AGENT_COMPOSER_RESERVE_SECONDS
            + QDRANT_SEARCH_RESERVE_SECONDS
            + RAG_EMBEDDING_TIMEOUT_SECONDS,
        )
        if rewrite_timeout >= 1:
            try:
                queries = rewrite_query_to_multi_queries(
                    question,
                    num_queries=RAG_MAX_RETRIEVAL_QUERIES,
                    timeout=rewrite_timeout,
                )
            except Exception as exc:
                logger.warning("Query rewrite failed: %s", exc)
                append_error(state, f"Query rewrite failed: {exc}")

    docs: List[Dict[str, Any]] = []
    seen = set()
    for query in queries:
        embedding_timeout = _bounded_timeout(
            state,
            RAG_EMBEDDING_TIMEOUT_SECONDS,
            AGENT_COMPOSER_RESERVE_SECONDS + QDRANT_SEARCH_RESERVE_SECONDS,
        )
        if embedding_timeout < 1:
            append_error(
                state,
                "RAG retrieval skipped because the request deadline was nearly exhausted",
            )
            break
        try:
            for doc in hybrid_search(
                query,
                limit=5,
                use_rerank=False,
                embedding_timeout=embedding_timeout,
            ):
                key = str(doc.get("doc_id") or doc.get("content") or doc.get("title") or "")
                if key and key not in seen:
                    seen.add(key)
                    doc["retrieval_query"] = query
                    docs.append(doc)
        except Exception as exc:
            logger.warning("Hybrid search failed for query '%s': %s", query, exc)
            append_error(state, f"Hybrid search failed: {exc}")
            break

    try:
        docs = rerank_documents(docs, question, top_n=5) if docs else []
    except Exception as exc:
        logger.warning("Rerank failed: %s", exc)
        append_error(state, f"Rerank failed: {exc}")
        docs = docs[:5]

    state["retrieved_docs"] = docs
    append_trace(
        state,
        RAG_AGENT,
        "retrieve_health_context",
        "success" if docs else "warning",
        f"Retrieved {len(docs)} Health/InBody context documents.",
    )
    return state


def web_search_agent(state: AgentState) -> AgentState:
    if WEB_SEARCH_AGENT not in state.get("selected_agents", []):
        return state

    question = _question(state)
    try:
        search_text = tavily_search_health(question, max_results=5)
        results = list(state.get("tool_results") or [])
        results.append({"agent": WEB_SEARCH_AGENT, "tool": "tavily_search_health", "result": search_text})
        state["tool_results"] = results
        append_trace(
            state,
            WEB_SEARCH_AGENT,
            "search_recent_health_web",
            "success",
            "Collected recent web context with Tavily.",
        )
    except Exception as exc:
        logger.warning("Web search failed: %s", exc)
        append_error(state, f"Web search failed: {exc}")
        append_trace(
            state,
            WEB_SEARCH_AGENT,
            "search_recent_health_web",
            "warning",
            "Web search failed; continuing without web context.",
        )
    return state


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


def _format_docs(docs: List[Dict[str, Any]]) -> str:
    if not docs:
        return "Không có tài liệu truy xuất phù hợp hoặc hệ thống search chưa sẵn sàng."
    lines = []
    for index, doc in enumerate(docs[:RAG_COMPOSER_MAX_DOCS], start=1):
        source = doc.get("source") or doc.get("source_file") or "unknown"
        title = doc.get("question") or doc.get("title") or f"Tài liệu {index}"
        content = doc.get("content") or doc.get("page_content") or ""
        lines.append(
            f"[{index}] Nguồn: {source}\n"
            f"Chủ đề: {title}\n"
            f"Nội dung: {content[:RAG_COMPOSER_MAX_CHARS_PER_DOC]}"
        )
    return "\n\n".join(lines)


def _fallback_answer(state: AgentState) -> str:
    chunks = [
        "Mình chưa thể hoàn tất phần diễn giải tự động trong thời gian cho phép."
    ]
    if state.get("tool_results"):
        missing_inputs = []
        for tool_result in state["tool_results"]:
            result = tool_result.get("result") or {}
            if isinstance(result, dict) and result.get("need_more_info"):
                message = result.get("message")
                if message and message not in missing_inputs:
                    missing_inputs.append(message)
        if missing_inputs:
            chunks.append("Dữ liệu còn thiếu:\n- " + "\n- ".join(missing_inputs))
    if state.get("retrieved_docs"):
        chunks.append(
            "Hệ thống đã tìm thấy {} tài liệu liên quan nhưng chưa tự tổng hợp "
            "để tránh diễn giải sai khi mô hình bị timeout. Bạn có thể thử lại "
            "hoặc hỏi ngắn hơn.".format(len(state["retrieved_docs"]))
        )
    context = _personalization_context(state)
    if context.get("has_profile") or context.get("has_latest_measurement"):
        chunks.append("Đã dùng hồ sơ/lần đo InBody gần nhất để cá nhân hóa khi câu hỏi thiếu dữ liệu.")
    safety = state.get("safety_result") or {}
    if safety:
        chunks.append("Lưu ý an toàn: {}".format(safety.get("disclaimer", "Thông tin chỉ mang tính tham khảo.")))
        if safety.get("risk_level") in {"urgent", "medical_caution"}:
            chunks.append(safety.get("recommended_action", "Nên tham khảo chuyên gia y tế khi cần."))
    return "\n\n".join(chunks)


def response_composer_agent(state: AgentState) -> AgentState:
    question = _question(state)
    selected = state.get("selected_agents") or []
    personalization = _personalization_context(state)
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là Response Composer Agent cho hệ thống Health/InBody Multi-Agent RAG. "
                "Hãy tổng hợp kết quả các agent thành câu trả lời tiếng Việt rõ ràng, an toàn, "
                "không chẩn đoán, không kê đơn, không thay thế bác sĩ."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Câu hỏi người dùng:\n{question}\n\n"
                f"Agent đã chạy:\n{', '.join(selected)}\n\n"
                f"Kết quả tool/agent:\n{_to_json(state.get('tool_results') or [])}\n\n"
                f"Hồ sơ cá nhân hóa hiện có:\n{_to_json(personalization)}\n\n"
                f"Safety result:\n{_to_json(state.get('safety_result') or {})}\n\n"
                f"Tài liệu RAG:\n{_format_docs(state.get('retrieved_docs') or [])}\n\n"
                "Yêu cầu: trả lời ngắn gọn nhưng đủ ý, nói rõ dữ liệu còn thiếu nếu có, "
                "nêu dữ liệu cá nhân hóa nào đã dùng nếu phù hợp, nêu hành động thực tế, "
                "và thêm lưu ý an toàn y tế."
            ),
        },
    ]
    composer_status = "success"
    composer_summary = "Composed final response from agent outputs."
    composer_timeout = _bounded_timeout(
        state,
        LLM_COMPOSER_TIMEOUT,
        reserve_seconds=0.25,
    )
    try:
        if composer_timeout < 1:
            raise TimeoutError(
                "Request deadline exhausted before response composition"
            )
        if GENERAL_CHAT_AGENT in selected and len(selected) == 1:
            final_answer = vietnamese_llm_chat_complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là trợ lý Health/InBody thân thiện. "
                            "Giới thiệu phạm vi hỗ trợ sức khỏe, InBody, dinh dưỡng và tập luyện."
                        ),
                    }
                ]
                + (state.get("history") or [])
                + [{"role": "user", "content": question}],
                max_tokens=min(256, LLM_COMPOSER_MAX_TOKENS),
                timeout=composer_timeout,
            )
        else:
            final_answer = openai_chat_complete(
                messages,
                max_tokens=LLM_COMPOSER_MAX_TOKENS,
                timeout=composer_timeout,
            )
    except Exception as exc:
        logger.warning("Response composition LLM failed: %s", exc)
        append_error(state, f"Response composition failed: {exc}")
        final_answer = _fallback_answer(state)
        composer_status = "warning"
        composer_summary = "LLM failed; returned deterministic safe fallback."

    state["final_answer"] = final_answer
    append_trace(
        state,
        RESPONSE_COMPOSER_AGENT,
        "compose_final_answer",
        composer_status,
        composer_summary,
    )
    return state


def _build_graph():
    if StateGraph is None:
        return None

    graph = StateGraph(AgentState)
    graph.add_node("normalize_question", normalize_question_agent)
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("inbody_agent", inbody_agent)
    graph.add_node("nutrition_agent", nutrition_agent)
    graph.add_node("training_agent", training_agent)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("web_search_agent", web_search_agent)
    graph.add_node("general_chat_agent", general_chat_agent)
    graph.add_node("safety_agent", safety_agent)
    graph.add_node("response_composer", response_composer_agent)

    graph.set_entry_point("normalize_question")
    graph.add_edge("normalize_question", "supervisor")
    graph.add_edge("supervisor", "inbody_agent")
    graph.add_edge("inbody_agent", "nutrition_agent")
    graph.add_edge("nutrition_agent", "training_agent")
    graph.add_edge("training_agent", "rag_agent")
    graph.add_edge("rag_agent", "web_search_agent")
    graph.add_edge("web_search_agent", "general_chat_agent")
    graph.add_edge("general_chat_agent", "safety_agent")
    graph.add_edge("safety_agent", "response_composer")
    graph.add_edge("response_composer", END)
    return graph.compile()


_COMPILED_GRAPH = None


def _run_sequential(state: AgentState) -> AgentState:
    for node in [
        normalize_question_agent,
        supervisor_agent,
        inbody_agent,
        nutrition_agent,
        training_agent,
        rag_agent,
        web_search_agent,
        general_chat_agent,
        safety_agent,
        response_composer_agent,
    ]:
        state = node(state)
    return state


def _response_from_state(state: AgentState) -> Dict[str, Any]:
    errors = state.get("errors") or []
    return {
        "role": "assistant",
        "content": state.get("final_answer") or _fallback_answer(state),
        "status": "degraded" if errors else "ok",
        "fast_path": state.get("fast_path"),
        "agent_trace": state.get("agent_trace") or [],
        "selected_agents": state.get("selected_agents") or [],
        "tool_results": state.get("tool_results") or [],
        "retrieved_docs": state.get("retrieved_docs") or [],
        "safety_result": state.get("safety_result") or {},
        "personalization_context": state.get("personalization_context") or {},
        "errors": errors,
    }


def multi_agent_handle(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[str] = None,
    user_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the Health/InBody Multi-Agent RAG graph and return answer plus trace."""
    global _COMPILED_GRAPH
    personalization_context = user_profile or {}
    initial_state: AgentState = {
        "user_id": user_id,
        "question": question,
        "history": history or [],
        "user_profile": personalization_context,
        "personalization_context": personalization_context,
        "latest_measurement": personalization_context.get("latest_measurement", {}),
        "tool_results": [],
        "retrieved_docs": [],
        "agent_trace": [],
        "errors": [],
        "deadline_monotonic": (
            time.monotonic() + AGENT_REQUEST_TIMEOUT_SECONDS
        ),
    }

    if personalization_context.get("error"):
        append_trace(
            initial_state,
            PERSONALIZATION_CONTEXT_AGENT,
            "load_user_context",
            "warning",
            "Personalization context was unavailable; continued without saved profile data.",
        )
    elif personalization_context.get("has_profile") or personalization_context.get("has_latest_measurement"):
        append_trace(
            initial_state,
            PERSONALIZATION_CONTEXT_AGENT,
            "load_user_context",
            "success",
            "Loaded saved user profile and/or latest InBody measurement.",
        )

    safety = check_medical_safety(question, _medical_conditions(initial_state))
    initial_state["safety_result"] = safety
    if safety.get("risk_level") == "urgent":
        return _response_from_state(_apply_urgent_fast_path(initial_state, safety))

    general_fast_path_state = _try_general_fast_path(initial_state)
    if general_fast_path_state is not None:
        return _response_from_state(general_fast_path_state)

    fast_path_state = _try_inbody_fast_path(initial_state)
    if fast_path_state is not None:
        return _response_from_state(fast_path_state)

    try:
        if StateGraph is not None:
            if _COMPILED_GRAPH is None:
                _COMPILED_GRAPH = _build_graph()
            final_state = _COMPILED_GRAPH.invoke(initial_state)
        else:
            append_trace(
                initial_state,
                "LangGraphRuntime",
                "load_langgraph",
                "warning",
                "LangGraph is unavailable; used sequential fallback runner.",
            )
            final_state = _run_sequential(initial_state)
    except Exception as exc:
        logger.error("Multi-agent graph failed: %s", exc)
        append_error(initial_state, f"Multi-agent graph failed: {exc}")
        append_trace(
            initial_state,
            "MultiAgentGraph",
            "run_graph",
            "error",
            "Graph failed; returned safe fallback answer.",
        )
        safety = check_medical_safety(question)
        initial_state["safety_result"] = safety
        initial_state["final_answer"] = _fallback_answer(initial_state)
        final_state = initial_state

    return _response_from_state(final_state)


def get_multi_agent_summary() -> Dict[str, Any]:
    return {
        "domain": "health_inbody",
        "orchestration": "LangGraph Multi-Agent RAG MVP",
        "entrypoint": "multi_agent_handle",
        "runtime_budget": {
            "request_timeout_seconds": AGENT_REQUEST_TIMEOUT_SECONDS,
            "composer_reserve_seconds": AGENT_COMPOSER_RESERVE_SECONDS,
            "rag_max_retrieval_queries": RAG_MAX_RETRIEVAL_QUERIES,
            "rag_embedding_timeout_seconds": RAG_EMBEDDING_TIMEOUT_SECONDS,
            "rag_composer_max_docs": RAG_COMPOSER_MAX_DOCS,
            "rag_composer_max_chars_per_doc": RAG_COMPOSER_MAX_CHARS_PER_DOC,
        },
        "agents": [
            {
                "name": PERSONALIZATION_CONTEXT_AGENT,
                "responsibility": "Load saved user profile and latest InBody measurement for personalization.",
            },
            {
                "name": SUPERVISOR_AGENT,
                "responsibility": "Select one or more specialist agents from the user question.",
            },
            {
                "name": INBODY_AGENT,
                "responsibility": "Calculate BMI and evaluate PBF/visceral fat from text metrics.",
            },
            {
                "name": RAG_AGENT,
                "responsibility": "Rewrite query, hybrid search Health/InBody corpus, rerank context.",
            },
            {
                "name": NUTRITION_AGENT,
                "responsibility": "Suggest protein range and calorie strategy.",
            },
            {
                "name": TRAINING_AGENT,
                "responsibility": "Suggest a basic weekly training plan.",
            },
            {
                "name": WEB_SEARCH_AGENT,
                "responsibility": "Search recent health web context when freshness is requested.",
            },
            {
                "name": SAFETY_AGENT,
                "responsibility": "Always run medical safety guardrail.",
            },
            {
                "name": RESPONSE_COMPOSER_AGENT,
                "responsibility": "Compose the final answer from agent outputs and safety context.",
            },
        ],
        "trace_schema": {
            "agent": "Agent name",
            "action": "Action performed",
            "status": "success | warning | error",
            "summary": "Short human-readable result",
        },
    }

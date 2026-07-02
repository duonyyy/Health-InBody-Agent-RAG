"""LangGraph-based Multi-Agent RAG MVP for Health/InBody chat."""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback keeps local dev usable without deps.
    END = "__end__"
    StateGraph = None

from brain import (
    AGENT_TOOLS_ROUTE,
    GENERAL_CHAT_ROUTE,
    HEALTH_RAG_ROUTE,
    WEB_SEARCH_ROUTE,
    detect_route,
    detect_user_intent,
    openai_chat_complete,
    vietnamese_llm_chat_complete,
)
from health_tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from query_rewriter import rewrite_query_to_multi_queries
from rerank import rerank_documents
from search import hybrid_search
from tavily_tool import tavily_search_health

from .parsing import (
    extract_height_cm,
    extract_pbf,
    extract_sex,
    extract_visceral_fat,
    extract_weight_kg,
    infer_days_per_week,
    infer_goal,
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


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _question(state: AgentState) -> str:
    return state.get("standalone_question") or state.get("question") or ""


def _ensure_agent(state: AgentState, agent_name: str) -> None:
    selected = list(state.get("selected_agents") or [])
    if agent_name not in selected:
        selected.append(agent_name)
    state["selected_agents"] = selected


def _has_any(text: str, keywords: List[str]) -> bool:
    text_lower = (text or "").lower()
    return any(keyword in text_lower for keyword in keywords)


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
    text = question.lower()
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
            "nên",
            "khác nhau",
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

    weight = extract_weight_kg(question)
    height = extract_height_cm(question)
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

    pbf = extract_pbf(question)
    if pbf is not None:
        result = evaluate_body_fat_percentage(pbf, extract_sex(question))
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

    visceral_fat = extract_visceral_fat(question)
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
    weight = extract_weight_kg(question) or 70
    goal = infer_goal(question)
    result = suggest_nutrition_goal(goal, weight)
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
    goal = infer_goal(question)
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
    try:
        queries = rewrite_query_to_multi_queries(question, num_queries=3)
    except Exception as exc:
        logger.warning("Query rewrite failed: %s", exc)
        queries = [question]
        append_error(state, f"Query rewrite failed: {exc}")

    docs: List[Dict[str, Any]] = []
    seen = set()
    for query in queries:
        try:
            for doc in hybrid_search(query, limit=5, use_rerank=False):
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
    question = _question(state)
    safety = check_medical_safety(question)
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
    for index, doc in enumerate(docs, start=1):
        source = doc.get("source") or doc.get("source_file") or "unknown"
        title = doc.get("question") or doc.get("title") or f"Tài liệu {index}"
        content = doc.get("content") or doc.get("page_content") or ""
        lines.append(f"[{index}] Nguồn: {source}\nChủ đề: {title}\nNội dung: {content[:1200]}")
    return "\n\n".join(lines)


def _fallback_answer(state: AgentState) -> str:
    question = _question(state)
    chunks = [
        "Mình đã xử lý câu hỏi theo luồng Multi-Agent RAG MVP.",
        f"Câu hỏi: {question}",
    ]
    if state.get("tool_results"):
        chunks.append("Kết quả công cụ:\n{}".format(_to_json(state["tool_results"])))
    if state.get("retrieved_docs"):
        chunks.append("Đã truy xuất {} tài liệu liên quan để tham khảo.".format(len(state["retrieved_docs"])))
    safety = state.get("safety_result") or {}
    if safety:
        chunks.append("Lưu ý an toàn: {}".format(safety.get("disclaimer", "Thông tin chỉ mang tính tham khảo.")))
        if safety.get("risk_level") in {"urgent", "medical_caution"}:
            chunks.append(safety.get("recommended_action", "Nên tham khảo chuyên gia y tế khi cần."))
    return "\n\n".join(chunks)


def response_composer_agent(state: AgentState) -> AgentState:
    question = _question(state)
    selected = state.get("selected_agents") or []
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
                f"Safety result:\n{_to_json(state.get('safety_result') or {})}\n\n"
                f"Tài liệu RAG:\n{_format_docs(state.get('retrieved_docs') or [])}\n\n"
                "Yêu cầu: trả lời ngắn gọn nhưng đủ ý, nói rõ dữ liệu còn thiếu nếu có, "
                "nêu hành động thực tế, và thêm lưu ý an toàn y tế."
            ),
        },
    ]
    try:
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
                + [{"role": "user", "content": question}]
            )
        else:
            final_answer = openai_chat_complete(messages)
    except Exception as exc:
        logger.warning("Response composition LLM failed: %s", exc)
        append_error(state, f"Response composition failed: {exc}")
        final_answer = _fallback_answer(state)

    state["final_answer"] = final_answer
    append_trace(
        state,
        RESPONSE_COMPOSER_AGENT,
        "compose_final_answer",
        "success",
        "Composed final response from agent outputs.",
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


def multi_agent_handle(question: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Run the Health/InBody Multi-Agent RAG graph and return answer plus trace."""
    global _COMPILED_GRAPH
    initial_state: AgentState = {
        "question": question,
        "history": history or [],
        "tool_results": [],
        "retrieved_docs": [],
        "agent_trace": [],
        "errors": [],
    }

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

    return {
        "role": "assistant",
        "content": final_state.get("final_answer") or _fallback_answer(final_state),
        "agent_trace": final_state.get("agent_trace") or [],
        "selected_agents": final_state.get("selected_agents") or [],
        "tool_results": final_state.get("tool_results") or [],
        "retrieved_docs": final_state.get("retrieved_docs") or [],
        "safety_result": final_state.get("safety_result") or {},
        "errors": final_state.get("errors") or [],
    }


def get_multi_agent_summary() -> Dict[str, Any]:
    return {
        "domain": "health_inbody",
        "orchestration": "LangGraph Multi-Agent RAG MVP",
        "entrypoint": "multi_agent_handle",
        "agents": [
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

"""Health Agent orchestration cho InBody RAG chatbot."""
import json
import logging
import re
from typing import Any, Dict, List, Optional

try:
    from celery import shared_task
except Exception:
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from brain import (
    AGENT_TOOLS_ROUTE,
    GENERAL_CHAT_ROUTE,
    HEALTH_RAG_ROUTE,
    WEB_SEARCH_ROUTE,
    detect_route,
    detect_user_intent,
    generate_health_answer,
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
from rerank import rerank_documents
from search import hybrid_search
from tavily_tool import tavily_qna, tavily_search_health

logger = logging.getLogger(__name__)


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _extract_number_after_patterns(text: str, patterns: List[str]) -> Optional[float]:
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except ValueError:
                continue
    return None


def _extract_weight_kg(text: str) -> Optional[float]:
    return _extract_number_after_patterns(
        text,
        [
            r"(\d+(?:[\.,]\d+)?)\s*kg",
            r"nặng\s*(\d+(?:[\.,]\d+)?)",
            r"cân nặng\s*(\d+(?:[\.,]\d+)?)",
        ],
    )


def _extract_height_cm(text: str) -> Optional[float]:
    height = _extract_number_after_patterns(
        text,
        [
            r"(\d+(?:[\.,]\d+)?)\s*cm",
            r"cao\s*(\d+(?:[\.,]\d+)?)",
            r"chiều cao\s*(\d+(?:[\.,]\d+)?)",
            r"(\d(?:[\.,]\d+)?)\s*m",
        ],
    )
    if height and height < 3:
        return height * 100
    return height


def _extract_pbf(text: str) -> Optional[float]:
    return _extract_number_after_patterns(
        text,
        [
            r"pbf\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"phần trăm mỡ\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"mỡ cơ thể\s*(?:là|=|:)?\s*(\d+(?:[\.,]\d+)?)\s*%",
        ],
    )


def _extract_visceral_fat(text: str) -> Optional[float]:
    return _extract_number_after_patterns(
        text,
        [
            r"mỡ nội tạng\s*(?:level|mức|là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
            r"visceral fat\s*(?:level|là|=|:)?\s*(\d+(?:[\.,]\d+)?)",
        ],
    )


def _extract_sex(text: str) -> Optional[str]:
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in [" nam ", "giới tính nam", "male"]):
        return "male"
    if any(keyword in text_lower for keyword in [" nữ ", "giới tính nữ", "female"]):
        return "female"
    return None


def bmi_tool(weight_kg: float, height_cm: float) -> str:
    """Tinh BMI tu can nang kg va chieu cao cm."""
    return _to_json(calculate_bmi(weight_kg, height_cm))


def body_fat_tool(pbf_percent: float, sex: Optional[str] = None) -> str:
    """Danh gia PBF/phan tram mo co the."""
    return _to_json(evaluate_body_fat_percentage(pbf_percent, sex))


def visceral_fat_tool(visceral_fat_level: float) -> str:
    """Danh gia muc mo noi tang tu bao cao InBody."""
    return _to_json(evaluate_visceral_fat(visceral_fat_level))


def nutrition_goal_tool(goal: str, weight_kg: float, activity_level: str = "moderate") -> str:
    """Goi y protein va chien luoc nang luong theo muc tieu."""
    return _to_json(suggest_nutrition_goal(goal, weight_kg, activity_level))


def training_plan_tool(
    goal: str,
    fitness_level: str = "beginner",
    days_per_week: int = 3,
) -> str:
    """Goi y lich tap co ban."""
    return _to_json(suggest_training_plan(goal, fitness_level, days_per_week))


def medical_safety_tool(question: str, conditions: Optional[List[str]] = None) -> str:
    """Kiem tra canh bao an toan y te."""
    return _to_json(check_medical_safety(question, conditions))


def health_web_search_tool(query: str, max_results: int = 5) -> str:
    """Tim kiem web cho suc khoe/InBody voi safety note."""
    return tavily_search_health(query, max_results=max_results)


def quick_answer_tool(question: str) -> str:
    """Tra loi nhanh bang Tavily Q&A."""
    return tavily_qna(question)


def rag_search_tool(query: str, top_k: int = 5) -> str:
    """Truy xuat tai lieu Health/InBody tu hybrid search."""
    docs = hybrid_search(query, limit=top_k)
    return _to_json(docs)


def _infer_goal(question: str) -> str:
    question_lower = question.lower()
    if "tăng cơ" in question_lower or "muscle" in question_lower:
        return "muscle_gain"
    if "duy trì" in question_lower or "maintenance" in question_lower:
        return "maintenance"
    return "fat_loss"


def _infer_days_per_week(question: str) -> int:
    match = re.search(r"(\d+)\s*(?:buổi|ngày)\s*/?\s*(?:tuần|week)", question.lower())
    if match:
        return max(1, min(7, int(match.group(1))))
    return 3


def _collect_tool_results(question: str) -> List[Dict[str, Any]]:
    """
    Goi cac health tools phu hop dua tren noi dung cau hoi.
    """
    text = question.lower()
    results = []

    safety = check_medical_safety(question)
    if safety.get("risk_level") in {"urgent", "medical_caution"}:
        results.append({"tool": "check_medical_safety", "result": safety})

    weight = _extract_weight_kg(question)
    height = _extract_height_cm(question)
    if ("bmi" in text or (weight and height)) and weight and height:
        results.append({"tool": "calculate_bmi", "result": calculate_bmi(weight, height)})
    elif "bmi" in text:
        results.append(
            {
                "tool": "calculate_bmi",
                "result": {
                    "need_more_info": True,
                    "message": "Cần cân nặng (kg) và chiều cao (cm) để tính BMI chính xác.",
                },
            }
        )

    pbf = _extract_pbf(question)
    if pbf is not None:
        results.append(
            {
                "tool": "evaluate_body_fat_percentage",
                "result": evaluate_body_fat_percentage(pbf, _extract_sex(question)),
            }
        )
    elif "pbf" in text or "phần trăm mỡ" in text:
        results.append(
            {
                "tool": "evaluate_body_fat_percentage",
                "result": {
                    "need_more_info": True,
                    "message": "Cần giá trị PBF (%) và tốt nhất có thêm giới tính/tuổi để đánh giá sát hơn.",
                },
            }
        )

    visceral_fat = _extract_visceral_fat(question)
    if visceral_fat is not None:
        results.append(
            {
                "tool": "evaluate_visceral_fat",
                "result": evaluate_visceral_fat(visceral_fat),
            }
        )
    elif "mỡ nội tạng" in text or "visceral" in text:
        results.append(
            {
                "tool": "evaluate_visceral_fat",
                "result": {
                    "need_more_info": True,
                    "message": "Cần visceral fat level/mức mỡ nội tạng trên báo cáo InBody.",
                },
            }
        )

    if "protein" in text or "dinh dưỡng" in text or "ăn" in text:
        results.append(
            {
                "tool": "suggest_nutrition_goal",
                "result": suggest_nutrition_goal(_infer_goal(question), weight or 70),
            }
        )

    if "lịch tập" in text or "tập luyện" in text or "cardio" in text or "kháng lực" in text:
        results.append(
            {
                "tool": "suggest_training_plan",
                "result": suggest_training_plan(
                    _infer_goal(question),
                    fitness_level="beginner",
                    days_per_week=_infer_days_per_week(question),
                ),
            }
        )

    return results


def _format_tool_answer(question: str, tool_results: List[Dict[str, Any]]) -> str:
    if not tool_results:
        tool_results = [{"tool": "check_medical_safety", "result": check_medical_safety(question)}]

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là Health Agent cho chatbot InBody. Hãy giải thích kết quả tool bằng tiếng Việt, "
                "ngắn gọn, an toàn, không chẩn đoán và không kê đơn."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Câu hỏi: {question}\n\n"
                f"Kết quả tool:\n{_to_json(tool_results)}\n\n"
                "Hãy trả lời dễ hiểu, nêu dữ liệu còn thiếu nếu có, và thêm lưu ý an toàn y tế."
            ),
        },
    ]
    try:
        return openai_chat_complete(messages)
    except Exception as e:
        logger.warning("LLM unavailable for tool explanation, returning raw tool result: %s", e)
        return _to_json(tool_results)


def _rag_answer(question: str) -> str:
    docs = hybrid_search(question, limit=8, use_rerank=False)
    ranked_docs = rerank_documents(docs, question, top_n=5)
    return generate_health_answer(question, ranked_docs, user_profile={})


def _web_answer(question: str) -> str:
    search_results = tavily_search_health(question, max_results=5)
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là Health Agent. Hãy tổng hợp kết quả web ở mức tham khảo, "
                "không chẩn đoán, không kê đơn, và nhắc gặp bác sĩ khi có dấu hiệu nguy hiểm."
            ),
        },
        {
            "role": "user",
            "content": f"Kết quả web:\n{search_results}\n\nCâu hỏi: {question}",
        },
    ]
    try:
        return openai_chat_complete(messages)
    except Exception as e:
        logger.warning("LLM unavailable for web answer, returning search results: %s", e)
        return search_results


def _general_answer(history: Optional[List[Dict[str, str]]], question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý Health/InBody thân thiện. Bạn hỗ trợ giải thích chỉ số InBody, "
                "dinh dưỡng, tập luyện và an toàn sức khỏe ở mức tham khảo."
            ),
        }
    ] + (history or []) + [{"role": "user", "content": question}]
    return vietnamese_llm_chat_complete(messages)


@shared_task()
def ai_agent_handle(question: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Backward-compatible wrapper for the Multi-Agent RAG MVP.
    """
    try:
        from agents import multi_agent_handle

        response = multi_agent_handle(question, history=history)
        return response.get("content", "")
    except Exception as e:
        logger.error("[HEALTH_AGENT] Error: %s", e)
        return (
            "Xin lỗi, mình chưa xử lý được câu hỏi này. "
            "Bạn có thể cung cấp rõ hơn chỉ số InBody, mục tiêu và tình trạng sức khỏe hiện tại."
        )


def get_agent_tools_summary() -> Dict:
    """Backward-compatible summary alias for the Multi-Agent RAG MVP."""
    from agents import get_multi_agent_summary

    return get_multi_agent_summary()

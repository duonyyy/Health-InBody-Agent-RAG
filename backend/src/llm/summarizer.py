"""Tom tat noi dung cho Health/InBody Agent RAG."""
import logging
import os
import re
from typing import List, Optional

from harness.budget import (
    BudgetExhaustedError,
    call_with_supported_kwargs,
    remaining_for_call,
)
from llm.client import LLM_TIMEOUT, openai_chat_complete

logger = logging.getLogger(__name__)
SUMMARIZE_DEFAULT_TIMEOUT = float(os.getenv("SUMMARIZE_TIMEOUT_SECONDS", "25"))

IMPORTANT_HEALTH_TERMS = [
    "inbody",
    "bmi",
    "pbf",
    "smm",
    "bfm",
    "mỡ nội tạng",
    "visceral fat",
    "protein",
    "calo",
    "dinh dưỡng",
    "tập luyện",
    "giảm mỡ",
    "tăng cơ",
    "bệnh nền",
    "bác sĩ",
    "triệu chứng",
    "an toàn",
]


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?。])\s+", text) if sentence.strip()]


def _extractive_summary(text: str, max_sentences: int = 4, max_chars: int = 900) -> str:
    """
    Fallback tom tat khong can LLM.

    Uu tien cac cau co thuat ngu Health/InBody va them canh bao an toan neu co.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return ""

    scored = []
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()
        score = sum(1 for term in IMPORTANT_HEALTH_TERMS if term in lower)
        score += 1 if index == 0 else 0
        scored.append((score, index, sentence))

    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_sentences]
    selected.sort(key=lambda item: item[1])

    summary = " ".join(sentence for _, _, sentence in selected)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."

    return summary


def summarize_text(
    text,
    max_sentences: int = 4,
    *,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    raise_on_timeout: bool = False,
) -> str:
    """
    Tom tat van ban tieng Viet theo domain Health/InBody.

    Ham uu tien LLM provider trong brain.py. Neu LLM chua san sang, fallback ve
    tom tat extractive de module van chay duoc trong moi truong dev/offline.
    """
    if not text or not str(text).strip():
        return ""

    effective_timeout = remaining_for_call(
        deadline_monotonic,
        SUMMARIZE_DEFAULT_TIMEOUT if timeout is None else timeout,
        default_timeout=min(SUMMARIZE_DEFAULT_TIMEOUT, float(LLM_TIMEOUT)),
    )
    if effective_timeout is None:
        if raise_on_timeout:
            raise BudgetExhaustedError("Summarization request budget exhausted")
        return _extractive_summary(text, max_sentences=max_sentences)

    prompt = f"""Bạn là trợ lý tóm tắt cho hệ thống Health/InBody Agent RAG.
Hãy tóm tắt nội dung sau bằng tiếng Việt, giữ các điểm quan trọng về chỉ số InBody,
dinh dưỡng, tập luyện và cảnh báo an toàn y tế nếu có.

Yêu cầu:
- Tối đa {max_sentences} câu.
- Không chẩn đoán bệnh, không kê đơn thuốc.
- Nếu nội dung có triệu chứng nguy hiểm hoặc bệnh nền, giữ lại khuyến nghị gặp bác sĩ.

Nội dung:
==================
{text}
==================

Tóm tắt:"""

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn tóm tắt nội dung sức khỏe/InBody một cách an toàn, ngắn gọn, "
                "không thêm thông tin ngoài văn bản."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        summary = call_with_supported_kwargs(
            openai_chat_complete,
            messages,
            temperature=0.0,
            max_tokens=300,
            timeout=effective_timeout,
            deadline_monotonic=deadline_monotonic,
        )
        return str(summary or "").strip()
    except Exception as e:
        is_timeout = isinstance(e, (BudgetExhaustedError, TimeoutError)) or "timeout" in type(e).__name__.lower()
        if raise_on_timeout and is_timeout:
            raise BudgetExhaustedError("Summarization timed out") from e
        logger.warning("LLM summarization unavailable, using extractive fallback: %s", type(e).__name__)
        return _extractive_summary(text, max_sentences=max_sentences)


def summarize_health_report(
    report_text: str,
    *,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
    raise_on_timeout: bool = False,
) -> str:
    """
    Tom tat rieng cho bao cao InBody/OCR.
    """
    return summarize_text(
        report_text,
        max_sentences=5,
        timeout=timeout,
        deadline_monotonic=deadline_monotonic,
        raise_on_timeout=raise_on_timeout,
    )

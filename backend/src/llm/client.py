"""LLM va embedding logic cho Health/InBody Agent RAG."""
import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

import requests

from core.http_client import get_shared_llm_session
from harness.budget import (
    BudgetExhaustedError,
    call_with_supported_kwargs,
    remaining_for_call,
    resolve_deadline,
)
from llm.embedding import get_custom_embedding

logger = logging.getLogger(__name__)


def _env_optional_bool(name: str, default: Optional[bool] = None) -> Optional[bool]:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"", "auto", "default", "none"}:
        return None
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{name} must be one of auto, true, or false; received {value!r}"
    )


def _normalize_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks.replace("đ", "d")).strip()


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "").strip()

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "none").lower()
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

_ORIGINAL_REQUESTS_POST = requests.post


def get_llm_http_session() -> requests.Session:
    """Tra ve HTTP Session co connection pool duoc tai su dung cho LLM."""
    return get_shared_llm_session()


def _post_llm_request(url: str, **kwargs) -> requests.Response:
    """Thuc hien HTTP POST toi LLM qua Connection Pool session, fallback sang requests.post neu duoc monkeypatch trong test."""
    if requests.post is not _ORIGINAL_REQUESTS_POST:
        return requests.post(url, **kwargs)
    session = get_llm_http_session()
    return session.post(url, **kwargs)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "").strip()
OLLAMA_THINK = _env_optional_bool("OLLAMA_THINK", None)
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "2048"))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))
LLM_ROUTER_MAX_TOKENS = int(os.environ.get("LLM_ROUTER_MAX_TOKENS", "16"))
LLM_ROUTER_TIMEOUT = int(os.environ.get("LLM_ROUTER_TIMEOUT", "8"))
LLM_NORMALIZE_MAX_TOKENS = int(os.environ.get("LLM_NORMALIZE_MAX_TOKENS", "96"))
LLM_NORMALIZE_TIMEOUT = int(os.environ.get("LLM_NORMALIZE_TIMEOUT", "10"))
LLM_REWRITE_MAX_TOKENS = int(os.environ.get("LLM_REWRITE_MAX_TOKENS", "128"))
LLM_REWRITE_TIMEOUT = int(os.environ.get("LLM_REWRITE_TIMEOUT", "15"))
LLM_COMPOSER_MAX_TOKENS = int(os.environ.get("LLM_COMPOSER_MAX_TOKENS", "96"))
LLM_COMPOSER_TIMEOUT = int(os.environ.get("LLM_COMPOSER_TIMEOUT", "35"))
LLM_FALLBACK_MIN_TIMEOUT_SECONDS = max(
    0.01, float(os.environ.get("LLM_FALLBACK_MIN_TIMEOUT_SECONDS", "0.05"))
)

VIETNAMESE_LLM_API_URL = os.environ.get("VIETNAMESE_LLM_API_URL")

HEALTH_RAG_ROUTE = "health_rag"
AGENT_TOOLS_ROUTE = "agent_tools"
WEB_SEARCH_ROUTE = "web_search"
GENERAL_CHAT_ROUTE = "general_chat"
VALID_ROUTES = {
    HEALTH_RAG_ROUTE,
    AGENT_TOOLS_ROUTE,
    WEB_SEARCH_ROUTE,
    GENERAL_CHAT_ROUTE,
}


def get_llm_runtime_config() -> Dict[str, Any]:
    """Return non-secret model/runtime policy for health checks and diagnostics."""
    if LLM_PROVIDER == "openai":
        model = OPENAI_MODEL or "not-configured"
    elif LLM_PROVIDER in {"custom", "vietnamese_llm"}:
        model = "custom-api"
    else:
        model = OLLAMA_MODEL or "not-configured"

    return {
        "provider": LLM_PROVIDER,
        "model": model,
        "ollama_think": "auto" if OLLAMA_THINK is None else OLLAMA_THINK,
        "ollama_num_ctx": OLLAMA_NUM_CTX,
        "task_budgets": {
            "router": {
                "max_tokens": LLM_ROUTER_MAX_TOKENS,
                "timeout_seconds": LLM_ROUTER_TIMEOUT,
            },
            "normalize": {
                "max_tokens": LLM_NORMALIZE_MAX_TOKENS,
                "timeout_seconds": LLM_NORMALIZE_TIMEOUT,
            },
            "rewrite": {
                "max_tokens": LLM_REWRITE_MAX_TOKENS,
                "timeout_seconds": LLM_REWRITE_TIMEOUT,
            },
            "composer": {
                "max_tokens": LLM_COMPOSER_MAX_TOKENS,
                "timeout_seconds": LLM_COMPOSER_TIMEOUT,
            },
        },
    }


def get_openai_client(timeout: Optional[float] = None, max_retries: int = 0):
    """Khoi tao OpenAI client neu co API key (tat SDK auto-retry de tranh chong retry)."""
    if not OPENAI_API_KEY:
        return None
    from openai import OpenAI

    kwargs: Dict[str, Any] = {
        "api_key": OPENAI_API_KEY,
        "max_retries": max(0, int(max_retries)),
    }
    if timeout is not None:
        kwargs["timeout"] = float(timeout)
    return OpenAI(**kwargs)


def _normalize_messages(messages=()) -> List[Dict[str, str]]:
    normalized = []
    for message in messages or []:
        if isinstance(message, dict):
            normalized.append(
                {
                    "role": message.get("role", "user"),
                    "content": str(message.get("content", "")),
                }
            )
        else:
            role = getattr(message, "role", "user")
            content = getattr(message, "content", "")
            normalized.append({"role": role, "content": str(content)})
    return normalized


def _chat_with_ollama(
    messages=(),
    model: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
    think: Optional[bool] = OLLAMA_THINK,
    timeout: float = LLM_TIMEOUT,
    deadline_monotonic: Optional[float] = None,
) -> str:
    selected_model = (model or OLLAMA_MODEL).strip()
    if not selected_model:
        raise RuntimeError("OLLAMA_MODEL is not configured")

    effective_timeout = remaining_for_call(
        deadline_monotonic,
        timeout,
        default_timeout=LLM_TIMEOUT,
    )
    if effective_timeout is None:
        raise BudgetExhaustedError("Ollama request budget exhausted")

    payload = {
        "model": selected_model,
        "messages": _normalize_messages(messages),
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    if think is not None:
        payload["think"] = think
    response = _post_llm_request(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        json=payload,
        timeout=effective_timeout,
    )
    response.raise_for_status()
    data = response.json()
    message = data.get("message", {})
    content = str(message.get("content") or "").strip()
    if not content:
        if message.get("thinking"):
            raise RuntimeError(
                "LLM returned thinking output without final content; adjust "
                "OLLAMA_THINK or the task token budget for the configured model"
            )
        raise RuntimeError("LLM returned an empty response")
    return content


def _chat_with_openai(
    messages=(),
    model: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
    raw: bool = False,
    timeout: float = LLM_TIMEOUT,
    deadline_monotonic: Optional[float] = None,
):
    effective_timeout = remaining_for_call(
        deadline_monotonic,
        timeout,
        default_timeout=LLM_TIMEOUT,
    )
    if effective_timeout is None:
        raise BudgetExhaustedError("OpenAI request budget exhausted")

    client = call_with_supported_kwargs(
        get_openai_client,
        timeout=effective_timeout,
        max_retries=0,
    )
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    selected_model = (model or OPENAI_MODEL).strip()
    if not selected_model:
        raise RuntimeError("OPENAI_MODEL is not configured")

    if hasattr(client, "with_options"):
        client = client.with_options(max_retries=0, timeout=effective_timeout)

    response = client.chat.completions.create(
        model=selected_model,
        messages=_normalize_messages(messages),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=effective_timeout,
    )
    if raw:
        return response.choices[0].message
    return response.choices[0].message.content


def _chat_with_custom_api(
    messages=(),
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
    timeout: float = LLM_TIMEOUT,
    deadline_monotonic: Optional[float] = None,
) -> str:
    if not VIETNAMESE_LLM_API_URL:
        raise RuntimeError("VIETNAMESE_LLM_API_URL is not configured")

    effective_timeout = remaining_for_call(
        deadline_monotonic,
        timeout,
        default_timeout=LLM_TIMEOUT,
    )
    if effective_timeout is None:
        raise BudgetExhaustedError("Custom LLM request budget exhausted")

    response = _post_llm_request(
        VIETNAMESE_LLM_API_URL,
        headers={"Content-Type": "application/json"},
        json={
            "messages": _normalize_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=effective_timeout,
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]


def openai_chat_complete(
    messages=(),
    model: Optional[str] = None,
    raw: bool = False,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS,
    think: Optional[bool] = OLLAMA_THINK,
    timeout: float = LLM_TIMEOUT,
    deadline_monotonic: Optional[float] = None,
):
    """
    Ham chat completion dung chung cho cac module cu.

    Ten ham duoc giu lai de tuong thich, nhung provider mac dinh cua project la
    Ollama theo config hien tai. Neu Ollama/custom API loi, ham se fallback sang
    OpenAI khi co OPENAI_API_KEY va con du deadline chung.
    """
    provider = LLM_PROVIDER
    logger.info("Chat completion provider=%s model=%s", provider, model)

    effective_deadline = resolve_deadline(
        timeout=timeout,
        deadline_monotonic=deadline_monotonic,
        default_timeout=LLM_TIMEOUT,
    )
    primary_timeout = remaining_for_call(
        effective_deadline,
        timeout,
        default_timeout=LLM_TIMEOUT,
    )
    if primary_timeout is None:
        raise BudgetExhaustedError("LLM request budget exhausted before primary call")

    try:
        if provider in {"none", "offline", "disabled"}:
            raise RuntimeError("LLM provider is disabled")
        if provider == "openai":
            return _chat_with_openai(
                messages,
                model=model or OPENAI_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                raw=raw,
                timeout=primary_timeout,
                deadline_monotonic=effective_deadline,
            )
        if provider in {"custom", "vietnamese_llm"}:
            if raw:
                raise ValueError("raw=True is not supported for custom API provider")
            return _chat_with_custom_api(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=primary_timeout,
                deadline_monotonic=effective_deadline,
            )

        if raw:
            raise ValueError("raw=True is only supported for OpenAI provider")
        return _chat_with_ollama(
            messages,
            model=model or OLLAMA_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            think=think,
            timeout=primary_timeout,
            deadline_monotonic=effective_deadline,
        )
    except Exception as e:
        logger.warning("Primary LLM provider failed: %s", e)
        if isinstance(e, (BudgetExhaustedError, ValueError)):
            raise
        if provider != "openai" and OPENAI_API_KEY:
            fallback_timeout = remaining_for_call(
                effective_deadline,
                timeout,
                default_timeout=LLM_TIMEOUT,
                min_timeout=LLM_FALLBACK_MIN_TIMEOUT_SECONDS,
            )
            if fallback_timeout is None:
                raise BudgetExhaustedError(
                    "LLM request budget exhausted before OpenAI fallback"
                ) from e
            return _chat_with_openai(
                messages,
                model=OPENAI_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                raw=raw,
                timeout=fallback_timeout,
                deadline_monotonic=effective_deadline,
            )
        raise


def vietnamese_llm_chat_complete(
    messages=(),
    temperature=0.2,
    max_tokens=LLM_MAX_TOKENS,
    think: Optional[bool] = OLLAMA_THINK,
    timeout: float = LLM_TIMEOUT,
    deadline_monotonic: Optional[float] = None,
):
    """
    Goi LLM tieng Viet cho Health/InBody chatbot.

    Giu ten ham cu de cac module khac khong bi vo khi import.
    """
    return openai_chat_complete(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        think=think,
        timeout=timeout,
        deadline_monotonic=deadline_monotonic,
    )


def get_embedding(text, model=None, timeout=None, deadline_monotonic=None, input_type="passage"):
    """
    Lay embedding cho truy xuat tai lieu Health/InBody.

    Args:
        text: Cau hoi hoac chunk can embed.
        model: Giu lai de tuong thich, custom_embedding se quyet dinh model.
    """
    if input_type not in {"query", "passage"}:
        raise ValueError("input_type must be query or passage")
    prefix = os.getenv("EMBEDDING_QUERY_PREFIX" if input_type == "query" else "EMBEDDING_PASSAGE_PREFIX", "")
    def prepare(item):
        return prefix + item.replace("\n", " ").strip()
    if isinstance(text, list):
        cleaned = [prepare(item) for item in text]
    else:
        cleaned = prepare(text)

    logger.info("Generating embedding for Health/InBody text")
    return call_with_supported_kwargs(
        get_custom_embedding,
        cleaned,
        timeout=timeout,
        deadline_monotonic=deadline_monotonic,
    )


def gen_doc_prompt(docs):
    """
    Tao prompt context tu danh sach tai lieu retrieval.
    """
    doc_prompt = ""
    for index, doc in enumerate(docs or [], start=1):
        question = doc.get("question") or doc.get("title") or f"Tài liệu {index}"
        content = doc.get("content") or doc.get("page_content") or ""
        source = doc.get("source") or doc.get("source_file") or "unknown"
        score = doc.get("relevance_score", doc.get("hybrid_score", ""))
        doc_prompt += (
            f"[{index}] Nguồn: {source}\n"
            f"Chủ đề/câu hỏi: {question}\n"
            f"Nội dung: {content}\n"
            f"Điểm liên quan: {score}\n\n"
        )

    return "Tài liệu tham khảo về sức khỏe/InBody:\n{}".format(doc_prompt)


def generate_conversation_text(conversations):
    conversation_text = ""
    for conversation in conversations or []:
        role = conversation.get("role", "user")
        content = conversation.get("content", "")
        conversation_text += f"{role}: {content}\n"
    return conversation_text


def _is_follow_up_question(message: str) -> bool:
    follow_up_indicators = [
        "đó",
        "này",
        "kia",
        "thế",
        "vậy",
        "nữa",
        "còn",
        "chỉ số đó",
        "mức này",
        "như vậy",
        "như thế",
    ]
    message_lower = (message or "").lower()
    return any(indicator in message_lower for indicator in follow_up_indicators)


def detect_user_intent(
    history,
    message,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
):
    """
    Viet lai cau hoi follow-up thanh cau hoi doc lap cho Health/InBody RAG.
    """
    if not history or (len(history) <= 1 and not _is_follow_up_question(message)):
        return message

    effective_timeout = remaining_for_call(
        deadline_monotonic,
        LLM_NORMALIZE_TIMEOUT if timeout is None else timeout,
        default_timeout=LLM_NORMALIZE_TIMEOUT,
    )
    if effective_timeout is None:
        logger.warning("Skipping follow-up normalization because request budget is exhausted")
        return message

    history_messages = generate_conversation_text(history)
    user_prompt = f"""Bạn là trợ lý AI cho Health/InBody Agent RAG.
Hãy viết lại câu hỏi hiện tại thành một câu hỏi độc lập, rõ ràng và đầy đủ ngữ cảnh bằng tiếng Việt.

Lịch sử hội thoại:
{history_messages}

Câu hỏi hiện tại: {message}

Yêu cầu:
1. Thay các đại từ như "nó", "đó", "này", "mức này" bằng đối tượng cụ thể.
2. Nếu ngữ cảnh nói về chỉ số InBody, nêu rõ BMI, PBF, SMM, BFM hoặc mỡ nội tạng.
3. Giữ đúng ý định của người dùng.
4. Không tự thêm chẩn đoán, thuốc hoặc thông tin y khoa không có trong hội thoại.
5. CHỈ trả về câu hỏi đã viết lại, KHÔNG giải thích.

Câu hỏi đã viết lại:"""

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn viết lại câu hỏi cho chatbot sức khỏe/InBody. "
                "Không chẩn đoán và không thêm thông tin ngoài ngữ cảnh."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    try:
        call_kwargs: Dict[str, Any] = {
            "temperature": 0.0,
            "max_tokens": LLM_NORMALIZE_MAX_TOKENS,
            "timeout": effective_timeout,
        }
        if deadline_monotonic is not None:
            call_kwargs["deadline_monotonic"] = deadline_monotonic
        rephrased = call_with_supported_kwargs(
            openai_chat_complete,
            messages,
            **call_kwargs,
        ).strip()
        return rephrased or message
    except Exception as e:
        logger.error("Error rephrasing Health/InBody question: %s", e)
        return message


def _keyword_route(message: str) -> str:
    message_lower = _normalize_match_text(message)

    general_keywords = ["xin chào", "hello", "hi", "cảm ơn", "thanks", "bạn là ai"]
    web_keywords = ["mới nhất", "gần đây", "hôm nay", "năm 2026", "vừa công bố"]
    tool_keywords = [
        "tính bmi",
        "bmi của tôi",
        "pbf",
        "mỡ nội tạng",
        "visceral fat",
        "gợi ý lịch tập",
        "lịch tập",
        "protein mỗi ngày",
        "bao nhiêu protein",
        "bệnh nền",
        "đau ngực",
        "khó thở",
    ]
    rag_keywords = [
        "inbody",
        "bmi",
        "smm",
        "bfm",
        "pbf",
        "giảm mỡ",
        "tăng cơ",
        "dinh dưỡng",
        "tập luyện",
        "mỡ nội tạng",
        "calo",
        "protein",
    ]

    def contains_any(keywords):
        for keyword in keywords:
            normalized_keyword = _normalize_match_text(keyword)
            if len(normalized_keyword) <= 2:
                if re.search(
                    rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)",
                    message_lower,
                ):
                    return True
            elif normalized_keyword in message_lower:
                return True
        return False

    if contains_any(general_keywords):
        return GENERAL_CHAT_ROUTE
    if contains_any(web_keywords):
        return WEB_SEARCH_ROUTE
    if contains_any(tool_keywords):
        return AGENT_TOOLS_ROUTE
    if contains_any(rag_keywords):
        return HEALTH_RAG_ROUTE
    return GENERAL_CHAT_ROUTE


def detect_route(
    history,
    message,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
):
    """
    Chon route xu ly cho Health/InBody chatbot.

    Routes:
    - health_rag: truy xuat tai lieu suc khoe, dinh duong, tap luyen, InBody.
    - agent_tools: can tinh BMI/PBF, danh gia mo noi tang, goi y nutrition/training.
    - web_search: thong tin moi can tra cuu web.
    - general_chat: chao hoi hoac ngoai pham vi.
    """
    effective_timeout = remaining_for_call(
        deadline_monotonic,
        LLM_ROUTER_TIMEOUT if timeout is None else timeout,
        default_timeout=LLM_ROUTER_TIMEOUT,
    )
    if effective_timeout is None:
        logger.warning("Skipping LLM route detection because request budget is exhausted")
        return _keyword_route(message)

    history_text = ""
    for msg in (history or [])[-4:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_text += f"{role}: {content}\n"

    prompt = f"""Bạn là bộ định tuyến cho Health/InBody Agent RAG.
Hãy phân loại câu hỏi hiện tại vào đúng một route.

Lịch sử hội thoại:
{history_text}

Câu hỏi hiện tại:
{message}

Routes:
1. "health_rag": hỏi kiến thức sức khỏe, dinh dưỡng, tập luyện, giải thích BMI/PBF/SMM/BFM/mỡ nội tạng từ tài liệu.
2. "agent_tools": cần tính toán hoặc đánh giá chỉ số cụ thể như BMI, PBF, mỡ nội tạng, protein/ngày, lịch tập, kiểm tra cảnh báo y tế.
3. "web_search": cần thông tin mới nhất, nghiên cứu/tin tức vừa công bố hoặc dữ liệu thời sự.
4. "general_chat": chào hỏi, cảm ơn, hỏi bot là ai, hoặc ngoài phạm vi.

Chỉ trả về một trong bốn giá trị: health_rag, agent_tools, web_search, general_chat.
Không giải thích.

Route:"""

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là router chính xác cho chatbot Health/InBody. "
                "Chỉ trả về route hợp lệ."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        call_kwargs: Dict[str, Any] = {
            "temperature": 0.0,
            "max_tokens": LLM_ROUTER_MAX_TOKENS,
            "timeout": effective_timeout,
        }
        if deadline_monotonic is not None:
            call_kwargs["deadline_monotonic"] = deadline_monotonic
        route = call_with_supported_kwargs(
            openai_chat_complete,
            messages,
            **call_kwargs,
        ).strip().lower()
        for valid_route in VALID_ROUTES:
            if valid_route in route:
                return valid_route
        logger.warning("Invalid LLM route '%s', using keyword fallback", route)
        return _keyword_route(message)
    except Exception as e:
        logger.error("Error detecting route, using keyword fallback: %s", e)
        return _keyword_route(message)


def build_health_answer_prompt(
    user_message: str,
    docs: Optional[List[Dict[str, Any]]] = None,
    user_profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Tao message prompt de sinh cau tra loi Health/InBody co guardrail."""
    context = gen_doc_prompt(docs or [])
    profile_text = json.dumps(user_profile or {}, ensure_ascii=False)

    system_prompt = """Bạn là trợ lý Health/InBody Agent RAG.
Bạn giúp người dùng hiểu chỉ số cơ thể, dinh dưỡng và tập luyện ở mức tham khảo.
Không chẩn đoán bệnh, không kê đơn thuốc, không thay thế bác sĩ.
Khi có triệu chứng nguy hiểm, thuốc, bệnh nền hoặc tình huống cấp cứu, hãy khuyên người dùng gặp bác sĩ/cơ sở y tế."""

    user_prompt = f"""Hồ sơ người dùng:
{profile_text}

{context}

Câu hỏi người dùng:
{user_message}

Yêu cầu trả lời:
- Trả lời tiếng Việt, rõ ràng, dễ hiểu.
- Dựa trên context nếu có; nếu thiếu dữ liệu thì nói rõ.
- Nêu khuyến nghị an toàn, thực tế, không cực đoan.
- Nếu dùng tài liệu, nhắc nguồn theo số [1], [2] khi phù hợp."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_health_answer(
    user_message: str,
    docs: Optional[List[Dict[str, Any]]] = None,
    user_profile: Optional[Dict[str, Any]] = None,
) -> str:
    messages = build_health_answer_prompt(user_message, docs, user_profile)
    return openai_chat_complete(messages)

"""Viet lai cau hoi cho Health/InBody Agent RAG."""
import logging
import re
from typing import List

logger = logging.getLogger(__name__)


HEALTH_EXPANSIONS = {
    "bmi": [
        "BMI",
        "chi so khoi co the",
        "chỉ số khối cơ thể",
        "thua can",
        "thiếu cân",
        "beo phi",
    ],
    "pbf": [
        "PBF",
        "phan tram mo co the",
        "phần trăm mỡ cơ thể",
        "body fat percentage",
        "ty le mo",
    ],
    "smm": [
        "SMM",
        "skeletal muscle mass",
        "khoi luong co xuong",
        "khối lượng cơ xương",
        "co bap",
    ],
    "bfm": [
        "BFM",
        "body fat mass",
        "khoi luong mo",
        "khối lượng mỡ",
        "mo co the",
    ],
    "mỡ nội tạng": [
        "mỡ nội tạng",
        "visceral fat",
        "visceral fat level",
        "mo bung",
        "rủi ro chuyển hóa",
    ],
    "giảm mỡ": [
        "giảm mỡ",
        "fat loss",
        "giam can",
        "thieu hut calo",
        "cardio",
        "tap khang luc",
    ],
    "tăng cơ": [
        "tăng cơ",
        "muscle gain",
        "hypertrophy",
        "tap khang luc",
        "protein",
        "phuc hoi",
    ],
    "dinh dưỡng": [
        "dinh dưỡng",
        "ăn uống",
        "calo",
        "protein",
        "carb",
        "chất béo",
        "khẩu phần",
    ],
    "lịch tập": [
        "lịch tập",
        "tập luyện",
        "khang luc",
        "cardio",
        "so buoi tap moi tuan",
        "phuc hoi",
    ],
    "bệnh nền": [
        "bệnh nền",
        "an toàn y tế",
        "canh bao suc khoe",
        "hoi bac si",
        "khong thay the chan doan",
    ],
}


def _clean_query_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\s*[-*]?\s*\d+[\.\)]\s*", "", line)
    line = re.sub(r"^\s*[-*]\s*", "", line)
    return line.strip()


def _chat_complete(messages: List[dict]) -> str:
    """
    Goi ham chat completion cua backend neu da duoc implement.

    brain.py hien con la skeleton trong project, nen helper nay giup module
    query_rewriter van import/test duoc va tu fallback khi LLM chua san sang.
    """
    try:
        from brain import openai_chat_complete

        return openai_chat_complete(messages)
    except Exception as e:
        logger.warning("Chat completion is not available for query rewriting: %s", e)
        raise


def expand_health_query(query: str) -> str:
    """
    Mo rong cau hoi bang cac thuat ngu suc khoe/InBody lien quan.

    Args:
        query: Cau hoi goc cua nguoi dung.

    Returns:
        Chuoi truy van da bo sung tu dong nghia de tang kha nang retrieval.
    """
    query_lower = query.lower()
    expanded_terms = [query]
    seen = {query_lower}

    for base_term, synonyms in HEALTH_EXPANSIONS.items():
        if base_term in query_lower:
            for synonym in synonyms:
                normalized = synonym.lower()
                if normalized not in seen:
                    expanded_terms.append(synonym)
                    seen.add(normalized)

    expanded_query = " ".join(expanded_terms[:12])
    if len(expanded_terms) > 1:
        logger.info(
            "Expanded health query from '%s' with %s related terms",
            query,
            len(expanded_terms) - 1,
        )
    return expanded_query


def expand_legal_query(query: str) -> str:
    """
    Backward-compatible alias cho prototype cu.

    New code should call expand_health_query.
    """
    return expand_health_query(query)


def rewrite_query_to_multi_queries(
    original_query: str, num_queries: int = 3, use_expansion: bool = True
) -> List[str]:
    """
    Viet lai mot cau hoi suc khoe/InBody thanh nhieu truy van retrieval.

    Cac query tao ra giup retriever bat duoc nhieu khia canh: chi so InBody,
    dinh duong, tap luyen, muc tieu ca nhan va canh bao an toan y te.

    Args:
        original_query: Cau hoi goc cua nguoi dung.
        num_queries: So query can tao.
        use_expansion: Co mo rong thuat ngu Health/InBody hay khong.

    Returns:
        Danh sach query da viet lai, uu tien giu query goc o dau danh sach.
    """
    expanded_query = (
        expand_health_query(original_query) if use_expansion else original_query
    )

    prompt = f"""Bạn là trợ lý AI cho hệ thống Health/InBody Agent RAG.
Nhiệm vụ của bạn là tạo {num_queries} câu truy vấn tiếng Việt khác nhau nhưng giữ đúng ý định câu hỏi gốc để truy xuất tài liệu sức khỏe, dinh dưỡng, tập luyện và giải thích chỉ số InBody.

Câu hỏi gốc: {original_query}
Từ khóa mở rộng: {expanded_query}

Yêu cầu:
1. Mỗi câu truy vấn diễn đạt theo một góc nhìn khác nhau.
2. Ưu tiên thuật ngữ liên quan đến InBody như BMI, PBF, SMM, BFM, mỡ nội tạng nếu phù hợp.
3. Nếu câu hỏi liên quan bệnh nền, thuốc, triệu chứng nguy hiểm hoặc chẩn đoán, hãy thêm sắc thái an toàn y tế.
4. Không đưa lời khuyên điều trị, không chẩn đoán bệnh.
5. Mỗi câu trên một dòng riêng.
6. KHÔNG đánh số, KHÔNG giải thích, CHỈ trả về {num_queries} câu truy vấn.

Ví dụ:
Câu hỏi gốc: "Tôi nên giảm mỡ hay tăng cơ trước?"
Kết quả:
Đánh giá chỉ số InBody để quyết định nên giảm mỡ hay tăng cơ trước
BMI PBF SMM mỡ nội tạng ảnh hưởng thế nào đến mục tiêu giảm mỡ tăng cơ
Khuyến nghị dinh dưỡng và tập luyện an toàn cho mục tiêu cải thiện thành phần cơ thể

Bây giờ hãy tạo {num_queries} câu truy vấn cho câu hỏi gốc trên:"""

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là chuyên gia viết lại truy vấn cho RAG sức khỏe/InBody. "
                "Bạn chỉ tạo truy vấn retrieval, không chẩn đoán và không kê đơn."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    logger.info("Rewriting health query: %s", original_query)

    try:
        response = _chat_complete(messages)
        queries = []

        for line in response.strip().split("\n"):
            cleaned_line = _clean_query_line(line)
            if cleaned_line and not cleaned_line.startswith("#"):
                queries.append(cleaned_line)

        if original_query not in queries:
            queries.insert(0, original_query)

        deduped_queries = []
        seen = set()
        for query in queries:
            key = query.lower()
            if key not in seen:
                deduped_queries.append(query)
                seen.add(key)

        while len(deduped_queries) < num_queries:
            deduped_queries.append(expanded_query)

        result = deduped_queries[:num_queries]
        logger.info("Generated %s health queries: %s", len(result), result)
        return result
    except Exception as e:
        logger.error("Error rewriting health query: %s", e)
        fallback = [original_query]
        if use_expansion:
            fallback.append(expanded_query)
        while len(fallback) < num_queries:
            fallback.append(original_query)
        return fallback[:num_queries]


def rewrite_query_with_context(query: str, conversation_history: List[dict]) -> str:
    """
    Viet lai cau hoi follow-up thanh cau hoi doc lap co ngu canh suc khoe/InBody.

    Args:
        query: Cau hoi hien tai.
        conversation_history: Lich su hoi thoai truoc do.

    Returns:
        Cau hoi doc lap, ro nghia hon cho retrieval.
    """
    if not conversation_history or len(conversation_history) <= 1:
        return query

    history_text = ""
    for msg in conversation_history[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            history_text += f"Người dùng: {content}\n"
        elif role == "assistant":
            history_text += f"Trợ lý: {content}\n"

    prompt = f"""Dựa vào lịch sử hội thoại dưới đây, hãy viết lại câu hỏi hiện tại thành một câu hỏi độc lập, rõ ràng và đầy đủ ý nghĩa bằng tiếng Việt cho hệ thống Health/InBody RAG.

Lịch sử hội thoại:
{history_text}

Câu hỏi hiện tại: {query}

Yêu cầu:
- Thay các đại từ như "nó", "cái đó", "chỉ số đó", "mức này" bằng đối tượng cụ thể.
- Giữ đúng ý định của người dùng.
- Nếu đang nói về chỉ số InBody, nêu rõ chỉ số như BMI, PBF, SMM, BFM hoặc mỡ nội tạng.
- Nếu có bệnh nền, thuốc hoặc triệu chứng nguy hiểm, giữ nguyên sắc thái cảnh báo y tế.
- CHỈ trả về câu hỏi đã viết lại, KHÔNG giải thích.

Câu hỏi đã viết lại:"""

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn viết lại câu hỏi follow-up cho chatbot sức khỏe/InBody. "
                "Không chẩn đoán, không thêm thông tin không có trong hội thoại."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    logger.info("Rewriting health query with context: %s", query)

    try:
        rewritten = _chat_complete(messages).strip()
        logger.info("Rewritten contextual health query: %s", rewritten)
        return rewritten or query
    except Exception as e:
        logger.error("Error rewriting health query with context: %s", e)
        return query

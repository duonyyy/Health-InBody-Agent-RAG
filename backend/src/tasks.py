"""Celery/background tasks cho Health/InBody Agent RAG."""
import logging
import uuid
from typing import Any, Dict, List, Optional

try:
    from celery import Celery

    celery_app = Celery(
        "health_inbody_tasks",
        broker="redis://valkey-db:6379/0",
        backend="redis://valkey-db:6379/0",
    )
    shared_task = celery_app.task
except Exception:
    celery_app = None

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
    get_embedding,
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
from search import hybrid_search, initialize_search_index
from tavily_tool import tavily_search_health

try:
    from utils import setup_logging

    setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "nmk_chatbot_collection"


def index_document_v2(
    id,
    question,
    content,
    collection_name=DEFAULT_COLLECTION_NAME,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Tach, embed va upsert mot tai lieu Health/InBody vao Qdrant.
    """
    from splitter import split_document
    from vectorize import add_vector

    text = f"{question or ''}\n{content or ''}".strip()
    chunks = split_document(
        text,
        metadata={
            "doc_id": id,
            "question": question,
            "source": (metadata or {}).get("source", "manual_index"),
            **(metadata or {}),
        },
    )

    vectors = {}
    for index, chunk in enumerate(chunks):
        vector = get_embedding(chunk.page_content)
        chunk_key = f"{id}-{index}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))
        vectors[point_id] = {
            "vector": vector,
            "payload": {
                **chunk.metadata,
                "question": question,
                "content": chunk.page_content,
                "chunk_id": chunk_key,
                "qdrant_point_id": point_id,
            },
        }

    if not vectors:
        return {"status": "no_chunks_created"}

    add_vector_status = add_vector(
        collection_name=collection_name,
        vectors=vectors,
    )
    logger.info("Indexed Health/InBody document %s with %s chunks", id, len(vectors))
    return add_vector_status


@shared_task()
def index_health_documents(documents: List[Dict[str, Any]], collection_name=DEFAULT_COLLECTION_NAME):
    """
    Index nhieu tai lieu Health/InBody va khoi tao BM25 search index.
    """
    statuses = []
    normalized_docs = []

    for index, doc in enumerate(documents or []):
        doc_id = doc.get("doc_id") or doc.get("id") or str(uuid.uuid4())
        question = doc.get("question") or doc.get("title") or ""
        content = doc.get("content") or doc.get("page_content") or ""
        metadata = {
            **(doc.get("metadata") or {}),
            "source": doc.get("source", "batch_index"),
            "content_type": doc.get("content_type"),
            "domain": doc.get("domain", "health_inbody"),
            "language": doc.get("language"),
            "title": doc.get("title"),
        }
        statuses.append(index_document_v2(doc_id, question, content, collection_name, metadata))
        normalized_docs.append(
            {
                "doc_id": doc_id,
                "question": question,
                "content": content,
                "source": metadata["source"],
                "content_type": metadata.get("content_type"),
                "domain": "health_inbody",
            }
        )

    initialize_search_index(normalized_docs)
    return {"indexed": len(statuses), "statuses": statuses}


# ==========================================
# CHAT HELPERS
# ==========================================

def _content_key(doc: Dict[str, Any]) -> str:
    return str(doc.get("doc_id") or doc.get("content") or doc.get("title") or "")


def follow_up_question(history, question):
    """Viet lai cau hoi follow-up thanh cau hoi doc lap."""
    standalone_question = detect_user_intent(history, question)
    logger.info("Standalone Health/InBody question: %s", standalone_question)
    return standalone_question


def _format_general_chat_prompt(history, question):
    system_prompt = """Bạn là trợ lý AI thân thiện của hệ thống Health/InBody Agent RAG.
Bạn có thể giúp người dùng hiểu chỉ số InBody, BMI, PBF, SMM, BFM, mỡ nội tạng,
dinh dưỡng, tập luyện và các lưu ý an toàn sức khỏe ở mức tham khảo.
Không chẩn đoán bệnh, không kê đơn thuốc và không thay thế bác sĩ."""

    return [{"role": "system", "content": system_prompt}] + (history or []) + [
        {"role": "user", "content": question}
    ]


def retrieve_with_hybrid_search(queries: List[str], top_k: int = 5) -> List[Dict]:
    """
    Truy xuat tai lieu Health/InBody bang multi-query hybrid search.
    """
    all_docs = []
    seen_keys = set()

    for query in queries:
        docs = hybrid_search(query, limit=top_k, use_rerank=False)
        for doc in docs:
            key = _content_key(doc)
            if key and key not in seen_keys:
                seen_keys.add(key)
                doc["retrieval_query"] = query
                all_docs.append(doc)

    logger.info(
        "Retrieved %s unique Health/InBody docs from %s queries",
        len(all_docs),
        len(queries),
    )
    return all_docs


def _agent_tools_answer(question: str) -> str:
    """
    Xu ly nhanh mot so cau hoi can tool tinh/danh gia.

    Agent.py hien chua hoan thien, nen tasks dung heuristic de goi tool phu hop
    cho cac demo Health/InBody co ban.
    """
    question_lower = question.lower()

    if "đau ngực" in question_lower or "khó thở" in question_lower or "bệnh nền" in question_lower:
        return str(check_medical_safety(question))

    if "mỡ nội tạng" in question_lower or "visceral" in question_lower:
        return (
            "Bạn đang hỏi về mỡ nội tạng. "
            "Hãy cung cấp visceral fat level trong báo cáo InBody để mình đánh giá chính xác hơn. "
            + str(evaluate_visceral_fat(10))
        )

    if "pbf" in question_lower or "phần trăm mỡ" in question_lower:
        return (
            "Bạn đang hỏi về PBF. "
            "Hãy cung cấp giá trị PBF (%) và giới tính để đánh giá sát hơn. "
            + str(evaluate_body_fat_percentage(25))
        )

    if "protein" in question_lower:
        return str(suggest_nutrition_goal("fat_loss", weight_kg=70))

    if "lịch tập" in question_lower or "tập luyện" in question_lower:
        return str(suggest_training_plan("fat_loss", fitness_level="beginner", days_per_week=3))

    if "bmi" in question_lower:
        return (
            "Hãy cung cấp cân nặng và chiều cao để tính BMI chính xác. "
            + str(calculate_bmi(weight_kg=70, height_cm=170))
        )

    return str(check_medical_safety(question))


def get_summarized_response(response):
    """
    Placeholder summarization hook.

    summarizer.py hien chua implement, nen tra ve response goc de tranh loi.
    """
    return response


# ==========================================
# CELERY CHAT TASKS
# ==========================================

@shared_task()
def bot_rag_answer_message(history, question):
    """
    Pipeline RAG cho Health/InBody:
    1. Viet lai follow-up question.
    2. Tao multi-query.
    3. Hybrid search.
    4. Rerank.
    5. Sinh cau tra loi co guardrail y te.
    """
    standalone_question = follow_up_question(history, question)
    query_variations = rewrite_query_to_multi_queries(standalone_question, num_queries=3)

    retrieved_docs = retrieve_with_hybrid_search(query_variations, top_k=5)
    ranked_docs = rerank_documents(retrieved_docs, standalone_question, top_n=5)

    answer = generate_health_answer(
        user_message=question,
        docs=ranked_docs,
        user_profile={},
    )
    logger.info("Generated Health/InBody RAG answer")
    return answer


@shared_task()
def bot_route_answer_message(history, question):
    """
    Route cau hoi den RAG, health tools, web search hoac general chat.
    """
    route = detect_route(history, question)
    logger.info("Selected Health/InBody route: %s", route)

    if route == HEALTH_RAG_ROUTE:
        return bot_rag_answer_message(history, question)

    if route == AGENT_TOOLS_ROUTE:
        standalone_question = follow_up_question(history, question)
        return _agent_tools_answer(standalone_question)

    if route == WEB_SEARCH_ROUTE:
        standalone_question = follow_up_question(history, question)
        search_results = tavily_search_health(standalone_question, max_results=5)
        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý Health/InBody. Hãy tổng hợp thông tin web ở mức tham khảo, "
                    "không chẩn đoán, không kê đơn và luôn nhắc gặp bác sĩ khi có dấu hiệu nguy hiểm."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Kết quả tìm kiếm:\n{search_results}\n\n"
                    f"Câu hỏi: {question}\n\nHãy trả lời ngắn gọn, an toàn và có nguồn nếu có."
                ),
            },
        ]
        return openai_chat_complete(messages)

    messages = _format_general_chat_prompt(history, question)
    return vietnamese_llm_chat_complete(messages)


@shared_task()
def llm_handle_message(bot_id, user_id, question):
    """
    Main handler toi gian cho Health/InBody chat.

    DB layer hien con placeholder, nen task nay tra ve response truc tiep thay vi
    luu conversation vao database.
    """
    logger.info("Start Health/InBody message handling bot_id=%s user_id=%s", bot_id, user_id)
    response = bot_route_answer_message([], question)
    return {"role": "assistant", "content": response}

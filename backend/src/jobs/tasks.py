"""Celery/background tasks cho Health/InBody Agent RAG."""
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from celery import Celery

    from core.config import (
        DEFAULT_CELERY_BROKER_URL,
        DEFAULT_CELERY_RESULT_BACKEND,
        DEFAULT_COLLECTION_NAME,
    )

    celery_app = Celery(
        "health_inbody_tasks",
        broker=DEFAULT_CELERY_BROKER_URL,
        backend=DEFAULT_CELERY_RESULT_BACKEND,
    )
    shared_task = celery_app.task
    celery_app.conf.result_expires = 3600
    celery_app.conf.beat_schedule = {"memory-retention-daily": {
        "task": "jobs.tasks.purge_memory", "schedule": 86400.0,
    }}
except Exception:
    from core.config import DEFAULT_COLLECTION_NAME

    celery_app = None

    def shared_task(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from llm.client import (
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
from rag.search import hybrid_search, initialize_search_index
from integrations.tavily import tavily_search_health
from agents import multi_agent_handle
from persistence.personalization_service import safe_build_confirmed_context

try:
    from core.utils import setup_logging

    setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def index_document_v2(
    id,
    question,
    content,
    collection_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    corpus_version: Optional[str] = None,
    qdrant_client: Any = None,
    require_allowlist: bool = False,
    lease: Any = None,
    lease_manager: Any = None,
) -> Dict[str, Any]:
    """
    Tach, embed va upsert mot tai lieu Health/InBody vao physical staging Qdrant collection.

    Tra ve WriteReceipt trung thuc; chan moi ghi vao serving alias hoac physical target dang phuc vu.
    """
    import hashlib
    from rag.corpus_lifecycle import (
        CorpusWriteValidationError,
        current_embedding_config,
        finalize_write_receipt,
        new_write_receipt,
        validate_vector_values,
        verify_staging_write_target,
    )
    from rag.corpus_policy import validate_shared_document
    from pipelines.import_data import split_document_safe
    from rag.qdrant.client import add_vector, client as default_qdrant_client

    active_qdrant = default_qdrant_client if qdrant_client is None else qdrant_client
    meta = dict(metadata or {})
    effective_version = corpus_version or meta.get("corpus_version") or None

    # R06: Fail-closed staging admission BEFORE splitting/embedding/writing.
    verify_staging_write_target(
        collection_name,
        qdrant_client=active_qdrant,
        corpus_version=effective_version,
        require_corpus_version=False,
        require_allowlist=require_allowlist,
        dry_run=False,
    )

    validate_shared_document({"question": question, "content": content, "metadata": meta})

    text = f"{question or ''}\n{content or ''}".strip()
    doc_id_str = str(id)
    chunks = split_document_safe(
        text,
        metadata={
            "doc_id": doc_id_str,
            "document_id": doc_id_str,
            "question": question,
            "source": meta.get("source", "manual_index"),
            **meta,
        },
        chunk_size=512,
        chunk_overlap=50,
    )

    emb_cfg = current_embedding_config()
    vectors = {}
    for index, chunk in enumerate(chunks):
        chunk_text = str(chunk.page_content or "")
        vector = get_embedding(chunk_text)
        validate_vector_values(vector, point_id=f"{doc_id_str}-{index}")
        chunk_key = f"{doc_id_str}-{index}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))
        content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        payload = {
            **chunk.metadata,
            "doc_id": doc_id_str,
            "document_id": doc_id_str,
            "question": question,
            "content": chunk_text,
            "chunk_id": chunk_key,
            "content_hash": content_hash,
            "qdrant_point_id": point_id,
            "embedding_fingerprint": emb_cfg["fingerprint"],
        }
        if effective_version:
            payload["corpus_version"] = effective_version
        vectors[point_id] = {
            "vector": vector,
            "payload": payload,
        }

    if not vectors:
        receipt = new_write_receipt(
            collection_name=str(collection_name),
            corpus_version=effective_version,
        )
        receipt["errors"].append({"document_id": doc_id_str, "error": "no_chunks_created"})
        return finalize_write_receipt(receipt)

    receipt = add_vector(
        collection_name=collection_name,
        vectors=vectors,
        raise_on_error=False,
        corpus_version=effective_version,
        embedding_fingerprint=emb_cfg["fingerprint"],
        enforce_staging_policy=True,
        require_corpus_version=False,
        require_allowlist=require_allowlist,
        lease=lease,
        lease_manager=lease_manager,
        qdrant_client=active_qdrant,
    )
    receipt["document_id"] = doc_id_str
    logger.info(
        "Indexed Health/InBody document %s into %s: ok=%s committed=%s failed=%s",
        doc_id_str,
        collection_name,
        receipt.get("ok"),
        receipt.get("committed_points"),
        receipt.get("failed_points"),
    )
    return receipt


@shared_task()
def index_health_documents(
    documents: List[Dict[str, Any]],
    collection_name: Optional[str] = None,
    *,
    corpus_version: Optional[str] = None,
    qdrant_client: Any = None,
    require_allowlist: bool = False,
    raise_on_error: bool = False,
    lock_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Index nhieu tai lieu Health/InBody vao physical staging collection voi write receipt trung thuc.

    Khong tu dong mutate BM25 in-memory index cua serving collection va khong bao thanh cong khi co loi batch.
    """
    from rag.corpus_lifecycle import (
        CorpusLeaseManager,
        QdrantWriteError,
        finalize_write_receipt,
        new_write_receipt,
        verify_staging_write_target,
    )
    from rag.corpus_policy import validate_shared_document
    from rag.qdrant.client import client as default_qdrant_client

    active_qdrant = default_qdrant_client if qdrant_client is None else qdrant_client
    verify_staging_write_target(
        collection_name,
        qdrant_client=active_qdrant,
        corpus_version=corpus_version,
        require_corpus_version=False,
        require_allowlist=require_allowlist,
        dry_run=False,
    )

    for document in documents or []:
        validate_shared_document(document)

    manager = CorpusLeaseManager(lock_dir=lock_dir)
    lease = manager.acquire_write_lease(
        str(collection_name),
        qdrant_client=active_qdrant,
        corpus_version=corpus_version,
        require_corpus_version=False,
        require_allowlist=require_allowlist,
    )

    aggregate = new_write_receipt(
        collection_name=str(collection_name),
        corpus_version=corpus_version,
    )
    statuses: List[Dict[str, Any]] = []
    attempted_documents = 0
    committed_documents = 0
    failed_documents = 0

    try:
        for doc in documents or []:
            attempted_documents += 1
            doc_id = str(doc.get("doc_id") or doc.get("id") or uuid.uuid4())
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
            if corpus_version and not metadata.get("corpus_version"):
                metadata["corpus_version"] = corpus_version
            try:
                doc_receipt = index_document_v2(
                    doc_id,
                    question,
                    content,
                    collection_name=collection_name,
                    metadata=metadata,
                    corpus_version=corpus_version,
                    qdrant_client=active_qdrant,
                    require_allowlist=require_allowlist,
                    lease=lease,
                    lease_manager=manager,
                )
            except Exception as exc:
                failed_documents += 1
                err_entry = {
                    "document_id": doc_id,
                    "ok": False,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                statuses.append(err_entry)
                aggregate["errors"].append(err_entry)
                aggregate["failed_points"] += 1
                aggregate["attempted_points"] += 1
                continue

            statuses.append(doc_receipt)
            aggregate["attempted_points"] += int(doc_receipt.get("attempted_points") or 0)
            aggregate["acknowledged_points"] += int(doc_receipt.get("acknowledged_points") or 0)
            aggregate["committed_points"] += int(doc_receipt.get("committed_points") or 0)
            aggregate["failed_points"] += int(doc_receipt.get("failed_points") or 0)
            aggregate["unconfirmed_points"] += int(doc_receipt.get("unconfirmed_points") or 0)
            aggregate["batches_attempted"] += int(doc_receipt.get("batches_attempted") or 0)
            aggregate["batches_committed"] += int(doc_receipt.get("batches_committed") or 0)
            aggregate["batches_unconfirmed"] += int(doc_receipt.get("batches_unconfirmed") or 0)
            aggregate["batches_failed"] += int(doc_receipt.get("batches_failed") or 0)
            aggregate["errors"].extend(doc_receipt.get("errors") or [])

            if doc_receipt.get("ok"):
                committed_documents += 1
            else:
                failed_documents += 1
    finally:
        manager.release_lease(lease)

    finalize_write_receipt(aggregate)
    if failed_documents > 0:
        aggregate["ok"] = False
        aggregate["status"] = "partial" if committed_documents > 0 else "failed"
        aggregate["partial_write"] = committed_documents > 0

    result = {
        **aggregate,
        "indexed": committed_documents,
        "attempted_documents": attempted_documents,
        "committed_documents": committed_documents,
        "failed_documents": failed_documents,
        "bm25_index_mutated": False,
        "statuses": statuses,
    }
    if raise_on_error and not result["ok"]:
        raise QdrantWriteError(
            f"Batch indexing failed/incomplete for {collection_name!r}: "
            f"committed_docs={committed_documents}, failed_docs={failed_documents}",
            receipt=result,
        )
    return result


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


CELERY_TASK_SOFT_TIME_LIMIT = max(
    5, min(55, int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", "50")))
)
CELERY_TASK_TIME_LIMIT = max(
    CELERY_TASK_SOFT_TIME_LIMIT + 5,
    min(60, int(os.getenv("CELERY_TASK_TIME_LIMIT_SECONDS", "60"))),
)


@shared_task(
    soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    time_limit=CELERY_TASK_TIME_LIMIT,
)
def llm_handle_message(
    bot_id,
    user_id,
    question,
    conversation_id=None,
    task_id=None,
    deadline_epoch: Optional[float] = None,
):
    """
    Main handler cho Health/InBody Multi-Agent RAG chat.

    Recheck persisted task ownership and use bounded PostgreSQL history.
    Honors shared queue+worker deadline when deadline_epoch is provided.
    """
    logger.info("Start Health/InBody message handling bot_id=%s", bot_id)
    from agents.constants import AGENT_MAX_REQUEST_TIMEOUT_SECONDS, AGENT_REQUEST_TIMEOUT_SECONDS
    from memory.chat import run_chat
    from memory.store import require_task_owner
    if task_id:
        require_task_owner(user_id, task_id)
    worker_budget = min(AGENT_REQUEST_TIMEOUT_SECONDS, AGENT_MAX_REQUEST_TIMEOUT_SECONDS, float(CELERY_TASK_SOFT_TIME_LIMIT))
    if deadline_epoch is not None:
        remaining = max(0.0, float(deadline_epoch) - time.time())
        worker_budget = min(worker_budget, remaining)
    deadline_monotonic = time.monotonic() + worker_budget
    return run_chat(
        question,
        user_id,
        conversation_id,
        bot_id=bot_id,
        deadline_monotonic=deadline_monotonic,
    )


@shared_task()
def purge_memory():
    from memory.store import purge_expired
    return purge_expired()

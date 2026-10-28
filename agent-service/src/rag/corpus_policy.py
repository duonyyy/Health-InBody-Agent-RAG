"""Public-corpus admission policy. Private memory never enters shared RAG."""
import os
import re
from urllib.parse import urlparse

PRIVATE_KEYS = {"user_id", "patient_id", "conversation_id", "session_id", "source_message_id",
                "medical_conditions", "medical_conditions_data", "latest_measurement", "profile", "memory_facts"}


def _private_keys(value) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in PRIVATE_KEYS
                   or (str(key).lower() == "data_scope" and item != "shared_knowledge")
                   or (str(key).lower() == "source" and str(item).lower() in
                       {"chat_history", "personal_memory", "user_profile", "zep_memory"})
                   or _private_keys(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_private_keys(item) for item in value)
    return False


def _text_values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _text_values(item)
    elif isinstance(value, str):
        yield value


def validate_shared_document(record: dict, *, require_review: bool = False) -> None:
    metadata = record.get("metadata") or {}
    scope = record.get("data_scope") or metadata.get("data_scope")
    if _private_keys(record) or (scope and scope != "shared_knowledge"):
        raise ValueError("Dữ liệu cá nhân không được đưa vào kho tri thức chung.")
    if any(re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:bệnh nhân|họ tên|số điện thoại)\s*:", content, re.I)
           for content in _text_values(record)):
        raise ValueError("Tài liệu có dấu hiệu định danh cá nhân; cần loại bỏ trước khi nạp.")
    if require_review:
        source = urlparse(str(record.get("source_url") or metadata.get("source_url") or ""))
        review = record.get("privacy_review_status") or metadata.get("privacy_review_status")
        if scope != "shared_knowledge" or review != "approved" or source.scheme not in {"https", "http"} or not source.netloc:
            raise ValueError("Cần nguồn công khai, phân loại shared_knowledge và privacy_review_status=approved.")


def require_staging_collection(name: str) -> str:
    allowed = {item.strip() for item in os.getenv("CORPUS_STAGING_COLLECTIONS", "").split(",") if item.strip()}
    serving = {os.getenv("QDRANT_COLLECTION_NAME", "nmk_chatbot_active"),
               os.getenv("QDRANT_COLLECTION_ALIAS", "nmk_chatbot_active")}
    if name not in allowed or name in serving:
        raise ValueError("Chỉ được ghi collection staging đã cấu hình; không ghi collection đang phục vụ.")
    return name

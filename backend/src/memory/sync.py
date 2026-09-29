"""Serialize external-memory lifecycle with PostgreSQL user-row locks.

The dirty marker commits before remote writes. A failed/partial sync cannot be
read, and revocation waits for any in-flight external operation to finish.
"""
from memory import store, zep_memory
from persistence import personalization_service as profiles
from persistence.models import User
import logging

logger = logging.getLogger(__name__)


def recall_confirmed(subject: str, query: str) -> str:
    if not zep_memory.available():
        return ""
    with store.session_scope() as db:
        user = store.locked_user(db, subject)
        flags = user.consent_flags or {}
        if not all(flags.get(key) for key in ("health_data_processing", "personalization", "external_memory")):
            return ""
        if flags.get("external_memory_sync_pending", True) or flags.get("external_memory_deletion_pending"):
            return ""
        facts = store.facts_for_context(db, user)
        if not facts:
            return ""
        # New chat text has not been confirmed for cloud storage/processing.
        # Send a category query, never the current health question.
        category = "response_preference dietary_preference exercise_preference"
        lowered = query.lower()
        if any(word in lowered for word in ("ăn", "dinh dưỡng", "thực phẩm")):
            category = "dietary_preference"
        elif any(word in lowered for word in ("tập", "đi bộ", "bơi")):
            category = "exercise_preference"
        return zep_memory.recall(subject, category, consent=True, facts=facts)


def sync_confirmed(subject: str) -> dict:
    if not zep_memory.available():
        raise profiles.PersonalizationConflict("Zep chưa được cấu hình hoặc đang tắt.")
    with store.session_scope() as db:
        user = store.locked_user(db, subject)
        store._require_consent(user, personalization=True)
        flags = user.consent_flags or {}
        if not flags.get("external_memory") or flags.get("external_memory_deletion_pending"):
            raise profiles.PersonalizationConflict("Bạn chưa bật bộ nhớ ngoài hoặc đang chờ xóa.")
        profiles._save_consent(user, {}, external_memory_sync_pending=True)
    with store.session_scope() as db:
        user = store.locked_user(db, subject)
        flags = user.consent_flags or {}
        if not flags.get("external_memory") or flags.get("external_memory_deletion_pending"):
            raise profiles.PersonalizationConflict("Quyền sử dụng bộ nhớ ngoài đã được thu hồi.")
        facts = store.facts_for_context(db, user)
        zep_memory.forget(subject)
        if facts:
            zep_memory.remember_confirmed(subject, facts, consent=True)
        profiles._save_consent(user, {}, external_memory_sync_pending=False,
                               external_memory_synced_at=store.now().isoformat())
        return {"status": "synced", "fact_count": len(facts)}


def finish_deletion(subject: str) -> None:
    with store.session_scope() as db:
        user = store.locked_user(db, subject)
        flags = user.consent_flags or {}
        if not flags.get("external_memory_deletion_pending"):
            return
        if flags.get("external_memory"):
            raise profiles.PersonalizationConflict("Bộ nhớ ngoài chưa được tắt.")
        zep_memory.forget(subject)
        profiles._save_consent(user, {"external_memory_deletion_pending": False},
                               external_memory_sync_pending=True,
                               external_memory_deleted_at=store.now().isoformat())


def maintain_external_memory() -> dict:
    """Daily worker retries pending deletion/sync without logging user data."""
    with store.session_scope() as db:
        users = db.query(User.external_id, User.consent_flags).filter(User.deleted_at.is_(None)).all()
    synced = failed = 0
    for subject, flags in users:
        flags = flags or {}
        try:
            if flags.get("external_memory_deletion_pending"):
                finish_deletion(subject)
                synced += 1
            elif flags.get("external_memory") and flags.get("external_memory_sync_pending") and zep_memory.available():
                sync_confirmed(subject)
                synced += 1
        except Exception as exc:
            failed += 1
            logger.warning("Memory maintenance deferred (%s)", type(exc).__name__)
    return {"external_operations_completed": synced, "external_operations_pending": failed}

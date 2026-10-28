"""Bounded chat history and explicit fact confirmation, always owner-scoped."""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from harness.guards import has_untrusted_instruction
from persistence.database import session_scope
from persistence.models import User, ChatSession, ChatMessage
from persistence import personalization_service as profiles
from memory.models import MemoryFact, ChatTask
from memory.history import bounded_history

FACT_KINDS = {"response_preference", "dietary_preference", "exercise_preference"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def retention_days() -> int:
    return max(1, min(30, int(os.getenv("CHAT_RETENTION_DAYS", "7"))))


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise profiles.PersonalizationNotFound() from exc


def locked_user(db, subject: str) -> User:
    user = db.query(User).filter(User.external_id == subject, User.deleted_at.is_(None)).with_for_update().first()
    if user is None:
        raise profiles.PersonalizationNotFound()
    return user


def _require_consent(user: User, *, personalization: bool = False) -> None:
    flags = profiles._consent(user)
    if not flags["health_data_processing"] or (personalization and not flags["personalization"]):
        raise profiles.PersonalizationConflict("Bạn cần đồng ý xử lý dữ liệu trước khi sử dụng bộ nhớ này.")


def _session(db, user: User, conversation_id: str) -> ChatSession:
    row = db.query(ChatSession).filter(ChatSession.id == _uuid(conversation_id), ChatSession.user_id == user.id).first()
    if row is None:
        raise profiles.PersonalizationNotFound()
    return row


def _prune(db, session_id) -> None:
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id,
                                ChatMessage.created_at < now() - timedelta(days=retention_days())).delete(synchronize_session=False)
    extra = db.query(ChatMessage.id).filter(ChatMessage.session_id == session_id).order_by(
        ChatMessage.created_at.desc(), ChatMessage.id.desc()).offset(40).all()
    if extra:
        db.query(ChatMessage).filter(ChatMessage.id.in_([row[0] for row in extra])).delete(synchronize_session=False)


def open_conversation(subject: str, bot_id: str = "health-inbody-agent") -> dict:
    with session_scope() as db:
        user = locked_user(db, subject)
        _require_consent(user)
        # A user cannot create unbounded empty sessions.
        old = db.query(ChatSession).filter(ChatSession.user_id == user.id).order_by(ChatSession.created_at.desc()).offset(19).all()
        for row in old:
            db.delete(row)
        row = ChatSession(user_id=user.id, external_user_id=subject, bot_id=bot_id[:128])
        db.add(row)
        db.flush()
        return {"conversation_id": str(row.id), "retention_days": retention_days()}


def load_history(subject: str, conversation_id: str) -> list[dict]:
    with session_scope() as db:
        user = locked_user(db, subject)
        session = _session(db, user, conversation_id)
        _require_consent(user)
        _prune(db, session.id)
        rows = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(
            ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(10).all()
        return bounded_history([{"role": row.role, "content": row.content} for row in reversed(rows)])


def record_turn(subject: str, conversation_id: str, question: str, answer: str) -> dict:
    with session_scope() as db:
        user = locked_user(db, subject)
        session = _session(db, user, conversation_id)
        _require_consent(user)
        stamp = now()
        user_message = ChatMessage(session_id=session.id, role="user", content=question[:4000], created_at=stamp)
        db.add(user_message)
        db.add(ChatMessage(session_id=session.id, role="assistant", content=answer[:4000],
                           created_at=stamp + timedelta(microseconds=1)))
        db.flush()
        _prune(db, session.id)
        return {"user_message_id": str(user_message.id)}


def delete_conversation(subject: str, conversation_id: str) -> None:
    with session_scope() as db:
        user = locked_user(db, subject)
        db.delete(_session(db, user, conversation_id))


def _fact_dict(row: MemoryFact) -> dict:
    return {"id": str(row.id), "kind": row.kind, "text": row.text, "status": row.status,
            "source_message_id": str(row.source_message_id) if row.source_message_id else None,
            "created_at": row.created_at.isoformat(),
            "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
            "expires_at": row.expires_at.isoformat()}


def facts_for_context(db, user: User) -> list[dict]:
    _require_consent(user, personalization=True)
    rows = db.query(MemoryFact).filter(MemoryFact.user_id == user.id, MemoryFact.status == "confirmed",
                                     MemoryFact.expires_at > now()).order_by(MemoryFact.confirmed_at.desc()).limit(20).all()
    return [_fact_dict(row) for row in rows if not has_untrusted_instruction(row.text)]


def confirmed_facts(subject: str) -> list[dict]:
    with session_scope() as db:
        return facts_for_context(db, locked_user(db, subject))


def list_facts(subject: str) -> dict:
    with session_scope() as db:
        user = locked_user(db, subject)
        _require_consent(user, personalization=True)
        rows = db.query(MemoryFact).filter(MemoryFact.user_id == user.id, MemoryFact.status != "rejected",
                                         MemoryFact.expires_at > now()).order_by(MemoryFact.created_at.desc()).limit(40).all()
        return {"items": [_fact_dict(row) for row in rows],
                "external_memory": bool((user.consent_flags or {}).get("external_memory")),
                "sync_pending": bool((user.consent_flags or {}).get("external_memory_sync_pending"))}


def propose_fact(subject: str, message_id: str, kind: str, text: str) -> dict:
    text = " ".join(text.split())
    if kind not in FACT_KINDS or not 3 <= len(text) <= 240 or has_untrusted_instruction(text):
        raise profiles.PersonalizationConflict("Nội dung ghi nhớ không hợp lệ.")
    if re.search(r"tôi bị|chẩn đoán|kê đơn|liều thuốc|\d\s*(?:kg|cm|mg|mmhg)", text, re.I):
        raise profiles.PersonalizationConflict("Chỉ số và bệnh sử cần được nhập/xác nhận trong hồ sơ sức khỏe.")
    with session_scope() as db:
        user = locked_user(db, subject)
        _require_consent(user, personalization=True)
        source = db.query(ChatMessage).join(ChatSession).filter(
            ChatMessage.id == _uuid(message_id), ChatMessage.role == "user", ChatSession.user_id == user.id,
            ChatMessage.created_at >= now() - timedelta(days=retention_days())).first()
        if source is None:
            raise profiles.PersonalizationNotFound()
        if text not in " ".join(source.content.split()):
            raise profiles.PersonalizationConflict("Đề xuất phải trích từ lời bạn đã gửi, không thêm thông tin mới.")
        existing = db.query(MemoryFact).filter(MemoryFact.user_id == user.id, MemoryFact.text == text,
                                             MemoryFact.status != "rejected", MemoryFact.expires_at > now()).first()
        if existing:
            return _fact_dict(existing)
        count = db.query(MemoryFact).filter(MemoryFact.user_id == user.id, MemoryFact.expires_at > now(),
                                          MemoryFact.status != "rejected").count()
        if count >= 40:
            raise profiles.PersonalizationConflict("Hãy xóa bớt đề xuất cũ trước khi thêm bộ nhớ mới.")
        row = MemoryFact(user_id=user.id, kind=kind, text=text, source_message_id=source.id,
                         status="pending", created_at=now(), expires_at=now() + timedelta(days=7))
        db.add(row)
        db.flush()
        return _fact_dict(row)


def _owned_fact(db, user, fact_id):
    row = db.query(MemoryFact).filter(MemoryFact.id == _uuid(fact_id), MemoryFact.user_id == user.id).first()
    if row is None:
        raise profiles.PersonalizationNotFound()
    return row


def confirm_fact(subject: str, fact_id: str) -> dict:
    with session_scope() as db:
        user = locked_user(db, subject)
        _require_consent(user, personalization=True)
        row = _owned_fact(db, user, fact_id)
        if row.status == "confirmed":
            return _fact_dict(row)
        if row.status != "pending" or row.expires_at.replace(tzinfo=timezone.utc) <= now():
            raise profiles.PersonalizationConflict("Đề xuất đã hết hạn hoặc bị từ chối.")
        if len(facts_for_context(db, user)) >= 20:
            raise profiles.PersonalizationConflict("Tối đa 20 ghi nhớ đã xác nhận; hãy xóa thông tin cũ.")
        row.status, row.confirmed_at = "confirmed", now()
        row.expires_at = now() + timedelta(days=180)
        profiles._save_consent(user, {}, external_memory_sync_pending=True)
        db.flush()
        return _fact_dict(row)


def delete_fact(subject: str, fact_id: str) -> None:
    with session_scope() as db:
        user = locked_user(db, subject)
        row = _owned_fact(db, user, fact_id)
        db.delete(row)
        profiles._save_consent(user, {}, external_memory_sync_pending=True)


def propose_from_turn(subject: str, message_id: str, question: str) -> list[dict]:
    candidates = []
    for sentence in re.split(r"[.!?\n]", question):
        sentence = sentence.strip()
        lowered = sentence.lower()
        kind = None
        if lowered.startswith("tôi thích") and ("câu trả lời" in lowered or "giải thích" in lowered):
            kind = "response_preference"
        elif lowered in {"tôi ăn chay", "mình ăn chay"}:
            kind = "dietary_preference"
        elif lowered.startswith(("tôi thích đi bộ", "tôi thích bơi", "tôi thích tập")):
            kind = "exercise_preference"
        if kind:
            candidates.append(propose_fact(subject, message_id, kind, sentence))
    return candidates[:3]


def create_task(subject: str) -> str:
    with session_scope() as db:
        user = profiles._get_user(db, subject, create=True)
        row = ChatTask(user_id=user.id, expires_at=now() + timedelta(hours=1))
        db.add(row)
        db.flush()
        return str(row.id)


def require_task_owner(subject: str, task_id: str) -> None:
    with session_scope() as db:
        row = db.query(ChatTask).join(User).filter(ChatTask.id == _uuid(task_id), User.external_id == subject,
                                                User.deleted_at.is_(None), ChatTask.expires_at > now()).first()
        if row is None:
            raise profiles.PersonalizationNotFound()


def purge_expired() -> dict:
    cutoff = now() - timedelta(days=retention_days())
    counts = {"messages_removed": 0, "tasks_removed": 0, "facts_removed": 0, "empty_sessions_removed": 0}
    with session_scope() as db:
        owners = db.query(ChatSession.user_id).join(ChatMessage).filter(ChatMessage.created_at < cutoff).union(
            db.query(MemoryFact.user_id).filter(MemoryFact.expires_at <= now()),
            db.query(ChatTask.user_id).filter(ChatTask.expires_at <= now()),
            db.query(ChatSession.user_id).filter(ChatSession.created_at < cutoff),
        ).all()
    # Same lock order as writers: user first, then owned records. Re-read expiry
    # after acquiring the lock so a concurrent confirmation is not removed.
    for (owner_id,) in owners:
        if owner_id is None:
            continue
        with session_scope() as db:
            user = db.query(User).filter(User.id == owner_id).with_for_update().first()
            if user is None:
                continue
            session_ids = db.query(ChatSession.id).filter(ChatSession.user_id == owner_id)
            counts["messages_removed"] += db.query(ChatMessage).filter(
                ChatMessage.session_id.in_(session_ids), ChatMessage.created_at < cutoff,
            ).delete(synchronize_session=False)
            counts["tasks_removed"] += db.query(ChatTask).filter(
                ChatTask.user_id == owner_id, ChatTask.expires_at <= now(),
            ).delete(synchronize_session=False)
            expired = db.query(MemoryFact).filter(MemoryFact.user_id == owner_id, MemoryFact.expires_at <= now()).all()
            if expired:
                profiles._save_consent(user, {}, external_memory_sync_pending=True)
                for fact in expired:
                    db.delete(fact)
                counts["facts_removed"] += len(expired)
            empty_sessions = db.query(ChatSession).filter(
                ChatSession.user_id == owner_id, ChatSession.created_at < cutoff, ~ChatSession.messages.any(),
            ).all()
            for session in empty_sessions:
                db.delete(session)
            counts["empty_sessions_removed"] += len(empty_sessions)
    return counts

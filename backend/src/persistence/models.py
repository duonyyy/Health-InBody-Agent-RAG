"""ORM models and small persistence helpers for Health/InBody backend."""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.database import Base, session_scope


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    sex: Mapped[Optional[str]] = mapped_column(String(32))
    birth_year: Mapped[Optional[int]] = mapped_column(Integer)
    height_cm: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    activity_level: Mapped[Optional[str]] = mapped_column(String(64))
    goal: Mapped[Optional[str]] = mapped_column(String(64))
    medical_conditions: Mapped[Optional[str]] = mapped_column(Text)

    measurements = relationship("InBodyMeasurement", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")


class InBodyMeasurement(Base, TimestampMixin):
    __tablename__ = "inbody_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False)
    height_cm: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    bmi: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    smm_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    bfm_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    pbf_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    visceral_fat_level: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    body_water_l: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    recommendation_goal: Mapped[Optional[str]] = mapped_column(String(64))
    source_file: Mapped[Optional[str]] = mapped_column(String(512))
    raw_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    user = relationship("User", back_populates="measurements")


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id: Mapped[str] = mapped_column(String(128), nullable=False, default="health-inbody-agent")
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    external_user_id: Mapped[Optional[str]] = mapped_column(String(128))
    title: Mapped[Optional[str]] = mapped_column(String(255))

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[Optional[str]] = mapped_column(String(64))
    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ChatSession", back_populates="messages")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(512))
    document_type: Mapped[Optional[str]] = mapped_column(String(128))
    content_type: Mapped[Optional[str]] = mapped_column(String(128))
    domain: Mapped[str] = mapped_column(String(128), nullable=False, default="health_inbody")
    document_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(128))
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    chunk_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="chunks")


class UploadedFile(Base, TimestampMixin):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024))
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    processing_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    parsed_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)


class InBodyMeasurementCreate(BaseModel):
    user_external_id: str
    measurement_date: date
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bmi: Optional[float] = None
    smm_kg: Optional[float] = None
    bfm_kg: Optional[float] = None
    pbf_percent: Optional[float] = None
    visceral_fat_level: Optional[float] = None
    body_water_l: Optional[float] = None
    recommendation_goal: Optional[str] = None
    source_file: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


class DocumentCreate(BaseModel):
    external_id: Optional[str] = None
    title: Optional[str] = None
    content: str
    source: Optional[str] = None
    document_type: Optional[str] = None
    content_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def get_or_create_chat_session(bot_id: str, external_user_id: str) -> uuid.UUID:
    with session_scope() as db:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.bot_id == bot_id,
                ChatSession.external_user_id == external_user_id,
            )
            .order_by(ChatSession.created_at.desc())
            .first()
        )
        if session is None:
            session = ChatSession(bot_id=bot_id, external_user_id=external_user_id)
            db.add(session)
            db.flush()
        return session.id


def update_chat_conversation(bot_id, user_id, message, is_user=True):
    """Persist a chat message and return the session id."""
    with session_scope() as db:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.bot_id == bot_id,
                ChatSession.external_user_id == str(user_id),
            )
            .order_by(ChatSession.created_at.desc())
            .first()
        )
        if session is None:
            session = ChatSession(bot_id=bot_id, external_user_id=str(user_id))
            db.add(session)
            db.flush()

        db.add(
            ChatMessage(
                session_id=session.id,
                role="user" if is_user else "assistant",
                content=message,
            )
        )
        return str(session.id)


def get_conversation_messages(conversation_id) -> List[Dict[str, str]]:
    with session_scope() as db:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [{"role": msg.role, "content": msg.content} for msg in messages]


def insert_document(question, content, source="api", doc_id=None):
    """Persist a RAG source document and return its database id."""
    with session_scope() as db:
        doc = Document(
            external_id=str(doc_id) if doc_id else None,
            title=question,
            content=content,
            source=source,
            domain="health_inbody",
        )
        db.add(doc)
        db.flush()
        return str(doc.id)

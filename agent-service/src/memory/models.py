"""Owner-scoped memory metadata. PostgreSQL remains authoritative."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from persistence.database import Base


class MemoryFact(Base):
    __tablename__ = "memory_facts"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'confirmed', 'rejected')", name="memory_fact_status"),
        Index("ix_memory_facts_owner_status", "user_id", "status", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("chat_messages.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatTask(Base):
    __tablename__ = "chat_tasks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

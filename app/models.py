import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    APPROVED = "approved"
    REVIEW = "review"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    document_type: Mapped[str] = mapped_column(String(30), default="unknown")
    document_number: Mapped[str | None] = mapped_column(String(100), index=True)
    vendor: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    document_date: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), index=True)
    duplicate_of_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    raw_text: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audits: Mapped[list["AuditEvent"]] = relationship(cascade="all, delete-orphan")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(100), default="system")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    error: Mapped[str] = mapped_column(Text)
    raw_text_excerpt: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    retry_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GmailAttachment(Base):
    __tablename__ = "gmail_attachments"
    __table_args__ = (
        UniqueConstraint("gmail_message_id", "gmail_attachment_id", name="uq_gmail_attachment"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    gmail_message_id: Mapped[str] = mapped_column(String(255), index=True)
    gmail_attachment_id: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(30))
    error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

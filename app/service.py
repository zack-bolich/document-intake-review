import hashlib
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditEvent, DeadLetter, Document, DocumentStatus
from app.parser import parse_document


def audit(db: Session, document_id: str, action: str, actor: str = "system", details: dict | None = None):
    db.add(AuditEvent(document_id=document_id, action=action, actor=actor, details=details or {}))


def ingest(db: Session, filename: str, data: bytes) -> Document:
    digest = hashlib.sha256(data).hexdigest()
    content_duplicate = db.scalar(select(Document).where(Document.content_hash == digest))
    try:
        parsed = parse_document(filename, data)
    except Exception as exc:
        dead = DeadLetter(
            filename=filename,
            content_hash=digest,
            error=str(exc),
            raw_text_excerpt="",
            payload=data,
        )
        db.add(dead)
        db.commit()
        raise ValueError(str(exc)) from exc

    business_duplicate = None
    number = parsed.fields.get("document_number")
    if number:
        business_duplicate = db.scalar(select(Document).where(
            Document.document_number == number,
            or_(Document.vendor == parsed.fields.get("vendor"), Document.vendor.is_(None)),
        ))
    duplicate = content_duplicate or business_duplicate
    if duplicate:
        status = DocumentStatus.DUPLICATE
    elif parsed.issues or parsed.confidence < get_settings().review_threshold:
        status = DocumentStatus.REVIEW
    else:
        status = DocumentStatus.APPROVED
    document = Document(
        filename=filename, content_hash=digest, raw_text=parsed.raw_text,
        confidence=parsed.confidence, field_confidence=parsed.field_confidence,
        status=status, duplicate_of_id=duplicate.id if duplicate else None, **parsed.fields,
    )
    if status == DocumentStatus.APPROVED:
        document.approved_at = datetime.now(UTC)
    db.add(document)
    db.flush()
    audit(db, document.id, "ingested", details={"issues": parsed.issues, "status": status.value})
    if duplicate:
        audit(db, document.id, "duplicate_detected", details={"duplicate_of_id": duplicate.id})
    db.commit()
    db.refresh(document)
    return document

"""Document-intake lifecycle and its transaction-owning interface."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditEvent, DeadLetter, Document, DocumentStatus, GmailAttachment
from app.parser import parse_document


class LifecycleError(Exception):
    """Expected failure at the Document-intake lifecycle seam."""


class DocumentNotFound(LifecycleError):
    pass


class DeadLetterNotFound(LifecycleError):
    pass


class ParseFailed(LifecycleError):
    pass


class RetryFailed(LifecycleError):
    pass


class DuplicateCannotBeApproved(LifecycleError):
    pass


class ApprovalFieldsMissing(LifecycleError):
    def __init__(self, missing_fields: list[str]):
        super().__init__(", ".join(missing_fields))
        self.missing_fields = missing_fields


@dataclass(frozen=True)
class GmailSource:
    message_id: str
    attachment_id: str


@dataclass(frozen=True)
class SourceAlreadyProcessed:
    outcome: str


@dataclass(frozen=True)
class DocumentChanges:
    values: dict[str, Any]

    def __post_init__(self) -> None:
        allowed = {
            "document_type",
            "document_number",
            "vendor",
            "amount",
            "currency",
            "document_date",
        }
        unknown = self.values.keys() - allowed
        if unknown:
            raise ValueError(f"Unsupported correction fields: {', '.join(sorted(unknown))}")


class DocumentIntakeLifecycle:
    """Own lifecycle invariants and persistence through approval."""

    def __init__(self, db: Session):
        self.db = db

    def intake(self, filename: str, data: bytes) -> Document:
        return self._intake(filename, data)

    def intake_gmail(
        self,
        filename: str,
        data: bytes,
        source: GmailSource,
    ) -> Document | SourceAlreadyProcessed:
        existing = self.gmail_source_result(source)
        if existing:
            return existing
        return self._intake(filename, data, source)

    def gmail_source_result(self, source: GmailSource) -> SourceAlreadyProcessed | None:
        existing = self._gmail_attachment(source)
        return SourceAlreadyProcessed(existing.outcome) if existing else None

    def record_gmail_failure(
        self,
        source: GmailSource,
        filename: str,
        error: str,
    ) -> SourceAlreadyProcessed | None:
        existing = self.gmail_source_result(source)
        if existing:
            return existing
        try:
            self.db.add(
                GmailAttachment(
                    gmail_message_id=source.message_id,
                    gmail_attachment_id=source.attachment_id,
                    filename=filename,
                    outcome=DocumentStatus.FAILED.value,
                    error=error,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return None

    def _intake(
        self,
        filename: str,
        data: bytes,
        source: GmailSource | None = None,
    ) -> Document:
        digest = hashlib.sha256(data).hexdigest()
        try:
            parsed = parse_document(filename, data)
        except Exception as exc:
            self.db.rollback()
            self._persist_parse_failure(filename, data, digest, str(exc), source)
            raise ParseFailed(str(exc)) from exc
        try:
            document, duplicate = self._prepare_document(filename, digest, parsed)
            return self._persist_document(document, parsed, duplicate, source=source)
        except Exception:
            self.db.rollback()
            raise

    def retry(self, dead_letter_id: str) -> Document:
        dead_letter = self.db.get(DeadLetter, dead_letter_id)
        if not dead_letter:
            raise DeadLetterNotFound(dead_letter_id)
        retry_count = dead_letter.retry_count + 1
        try:
            parsed = parse_document(dead_letter.filename, dead_letter.payload)
        except Exception as exc:
            self.db.rollback()
            canonical = self.db.get(DeadLetter, dead_letter_id)
            if not canonical:
                raise DeadLetterNotFound(dead_letter_id) from exc
            try:
                canonical.retry_count = retry_count
                canonical.error = str(exc)
                canonical.updated_at = datetime.now(UTC)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            raise RetryFailed(str(exc)) from exc
        try:
            document, duplicate = self._prepare_document(
                dead_letter.filename,
                dead_letter.content_hash,
                parsed,
            )
            return self._persist_document(
                document,
                parsed,
                duplicate,
                retry_dead_letter=dead_letter,
                retry_count=retry_count,
            )
        except Exception:
            self.db.rollback()
            raise

    def correct(
        self,
        document_id: str,
        changes: DocumentChanges,
        *,
        actor: str,
    ) -> Document:
        document = self.db.get(Document, document_id)
        if not document:
            raise DocumentNotFound(document_id)
        before = {key: str(getattr(document, key)) for key in changes.values}
        try:
            for key, value in changes.values.items():
                setattr(document, key, value)
            self._add_audit(
                document.id,
                "corrected",
                actor,
                {"before": before, "changed_fields": list(changes.values)},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(document)
        return document

    def approve(self, document_id: str, *, actor: str) -> Document:
        document = self.db.get(Document, document_id)
        if not document:
            raise DocumentNotFound(document_id)
        if document.status == DocumentStatus.DUPLICATE:
            raise DuplicateCannotBeApproved(document_id)
        missing = [
            name
            for name in ("vendor", "amount", "document_date", "document_number")
            if not getattr(document, name)
        ]
        if missing:
            raise ApprovalFieldsMissing(missing)
        try:
            document.status = DocumentStatus.APPROVED
            document.approved_at = datetime.now(UTC)
            self._add_audit(document.id, "approved", actor)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(document)
        return document

    def audit(self, document_id: str) -> list[AuditEvent]:
        if not self.db.get(Document, document_id):
            raise DocumentNotFound(document_id)
        return list(
            self.db.scalars(
                select(AuditEvent)
                .where(AuditEvent.document_id == document_id)
                .order_by(AuditEvent.created_at)
            )
        )

    def _add_audit(
        self,
        document_id: str,
        action: str,
        actor: str = "system",
        details: dict | None = None,
    ) -> None:
        self.db.add(
            AuditEvent(
                document_id=document_id,
                action=action,
                actor=actor,
                details=details or {},
            )
        )

    def _prepare_document(self, filename: str, digest: str, parsed):
        content_duplicate = self.db.scalar(
            select(Document).where(Document.content_hash == digest)
        )
        business_duplicate = None
        number = parsed.fields.get("document_number")
        vendor = parsed.fields.get("vendor")
        if number and vendor:
            business_duplicate = self.db.scalar(
                select(Document).where(
                    Document.document_number == number,
                    Document.vendor == vendor,
                )
            )
        duplicate = content_duplicate or business_duplicate
        if duplicate:
            status = DocumentStatus.DUPLICATE
        elif parsed.issues or parsed.confidence < get_settings().review_threshold:
            status = DocumentStatus.REVIEW
        else:
            status = DocumentStatus.APPROVED
        document = Document(
            filename=filename,
            content_hash=digest,
            raw_text=parsed.raw_text,
            confidence=parsed.confidence,
            field_confidence=parsed.field_confidence,
            status=status,
            duplicate_of_id=duplicate.id if duplicate else None,
            **parsed.fields,
        )
        if status == DocumentStatus.APPROVED:
            document.approved_at = datetime.now(UTC)
        return document, duplicate

    def _persist_document(
        self,
        document: Document,
        parsed,
        duplicate: Document | None,
        *,
        source: GmailSource | None = None,
        retry_dead_letter: DeadLetter | None = None,
        retry_count: int | None = None,
    ) -> Document:
        try:
            self.db.add(document)
            self.db.flush()
            self._add_audit(
                document.id,
                "ingested",
                details={"issues": parsed.issues, "status": document.status.value},
            )
            if duplicate:
                self._add_audit(
                    document.id,
                    "duplicate_detected",
                    details={"duplicate_of_id": duplicate.id},
                )
            if source:
                self.db.add(
                    GmailAttachment(
                        gmail_message_id=source.message_id,
                        gmail_attachment_id=source.attachment_id,
                        filename=document.filename,
                        document_id=document.id,
                        outcome=document.status.value,
                    )
                )
            if retry_dead_letter:
                self.db.delete(retry_dead_letter)
                self._add_audit(
                    document.id,
                    "retried_from_dead_letter",
                    details={"retry_count": retry_count},
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(document)
        return document

    def _persist_parse_failure(
        self,
        filename: str,
        data: bytes,
        digest: str,
        error: str,
        source: GmailSource | None,
    ) -> None:
        try:
            self.db.add(
                DeadLetter(
                    filename=filename,
                    content_hash=digest,
                    error=error,
                    raw_text_excerpt="",
                    payload=data,
                )
            )
            if source:
                self.db.add(
                    GmailAttachment(
                        gmail_message_id=source.message_id,
                        gmail_attachment_id=source.attachment_id,
                        filename=filename,
                        outcome=DocumentStatus.FAILED.value,
                        error=error,
                    )
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _gmail_attachment(self, source: GmailSource) -> GmailAttachment | None:
        return self.db.scalar(
            select(GmailAttachment).where(
                GmailAttachment.gmail_message_id == source.message_id,
                GmailAttachment.gmail_attachment_id == source.attachment_id,
            )
        )

import hashlib
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.database import SessionLocal
from app.document_lifecycle import (
    ApprovalFieldsMissing,
    DocumentChanges,
    DocumentIntakeLifecycle,
    DuplicateCannotBeApproved,
    GmailSource,
    ParseFailed,
    RetryFailed,
    SourceAlreadyProcessed,
)
from app.models import AuditEvent, DeadLetter, Document, DocumentStatus, GmailAttachment


def test_intake_approves_and_audits_a_complete_document(invoice_pdf):
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        document = lifecycle.intake("invoice.pdf", invoice_pdf)

        assert document.status == DocumentStatus.APPROVED
        assert document.document_number == "INV-3001"
        assert [event.action for event in lifecycle.audit(document.id)] == ["ingested"]


def test_failed_retry_updates_the_canonical_dead_letter():
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)
        with pytest.raises(ParseFailed):
            lifecycle.intake("broken.pdf", b"not-a-pdf")
        original = db.query(DeadLetter).one()

        with pytest.raises(RetryFailed):
            lifecycle.retry(original.id)

        dead_letters = db.query(DeadLetter).all()
        assert [dead.id for dead in dead_letters] == [original.id]
        assert dead_letters[0].retry_count == 1


def test_successful_retry_removes_dead_letter_and_records_audit(invoice_pdf):
    with SessionLocal() as db:
        dead_letter = DeadLetter(
            filename="invoice.pdf",
            content_hash=hashlib.sha256(invoice_pdf).hexdigest(),
            error="temporary extraction failure",
            payload=invoice_pdf,
        )
        db.add(dead_letter)
        db.commit()
        dead_letter_id = dead_letter.id

        document = DocumentIntakeLifecycle(db).retry(dead_letter_id)

        assert db.get(DeadLetter, dead_letter_id) is None
        assert [event.action for event in DocumentIntakeLifecycle(db).audit(document.id)] == [
            "ingested",
            "retried_from_dead_letter",
        ]


def test_content_and_business_duplicates_use_the_lifecycle_seam(invoice_pdf):
    changed_data = b"""Invoice
Invoice Number: INV-3001
Vendor: Northstar Office Supply
Amount: 999.00
Date: 2026-07-21
"""
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)
        original = lifecycle.intake("original.pdf", invoice_pdf)
        content_duplicate = lifecycle.intake("copy.pdf", invoice_pdf)
        business_duplicate = lifecycle.intake("changed.txt", changed_data)

        assert content_duplicate.duplicate_of_id == original.id
        assert business_duplicate.duplicate_of_id == original.id
        assert content_duplicate.status == DocumentStatus.DUPLICATE
        assert business_duplicate.status == DocumentStatus.DUPLICATE

        with pytest.raises(DuplicateCannotBeApproved):
            lifecycle.approve(content_duplicate.id, actor="reviewer")


def test_reviewer_corrects_then_approves_through_the_lifecycle():
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)
        document = lifecycle.intake(
            "partial.txt",
            b"INVOICE\nVendor: Synthetic Repairs\nInvoice Number: INV-LOW-1",
        )
        assert document.status == DocumentStatus.REVIEW

        with pytest.raises(ApprovalFieldsMissing) as failure:
            lifecycle.approve(document.id, actor="reviewer")
        assert failure.value.missing_fields == ["amount", "document_date"]

        corrected = lifecycle.correct(
            document.id,
            DocumentChanges(
                {
                    "amount": Decimal("87.20"),
                    "currency": "USD",
                    "document_date": date(2026, 7, 17),
                }
            ),
            actor="portfolio-reviewer",
        )
        approved = lifecycle.approve(corrected.id, actor="portfolio-reviewer")

        assert approved.status == DocumentStatus.APPROVED
        assert [event.action for event in lifecycle.audit(document.id)] == [
            "ingested",
            "corrected",
            "approved",
        ]


def test_gmail_intake_is_atomic_and_idempotent(invoice_pdf):
    source = GmailSource("message-1", "attachment-1")
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        document = lifecycle.intake_gmail("invoice.pdf", invoice_pdf, source)
        repeated = lifecycle.intake_gmail("invoice.pdf", invoice_pdf, source)

        assert isinstance(repeated, SourceAlreadyProcessed)
        trackers = db.query(GmailAttachment).all()
        assert len(trackers) == 1
        assert trackers[0].document_id == document.id
        assert trackers[0].outcome == DocumentStatus.APPROVED.value


def test_gmail_parse_failure_persists_dead_letter_and_source_together():
    source = GmailSource("message-failed", "attachment-failed")
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        with pytest.raises(ParseFailed):
            lifecycle.intake_gmail("broken.pdf", b"not-a-pdf", source)

        assert db.query(DeadLetter).count() == 1
        tracker = db.query(GmailAttachment).one()
        assert tracker.document_id is None
        assert tracker.outcome == DocumentStatus.FAILED.value


def test_pre_intake_gmail_failure_is_recorded_once():
    source = GmailSource("message-download", "attachment-download")
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        assert lifecycle.record_gmail_failure(source, "invoice.pdf", "decode failed") is None
        repeated = lifecycle.record_gmail_failure(source, "invoice.pdf", "decode failed")

        assert isinstance(repeated, SourceAlreadyProcessed)
        assert db.query(GmailAttachment).count() == 1


def test_unexpected_audit_failure_rolls_back_the_document(invoice_pdf):
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        def fail_audit(_session, _context, _instances):
            if any(isinstance(item, AuditEvent) for item in db.new):
                raise RuntimeError("audit persistence failed")

        event.listen(db, "before_flush", fail_audit)
        try:
            with pytest.raises(RuntimeError, match="audit persistence failed"):
                lifecycle.intake("invoice.pdf", invoice_pdf)
        finally:
            event.remove(db, "before_flush", fail_audit)

        assert db.query(Document).count() == 0
        assert db.query(AuditEvent).count() == 0


def test_dead_letter_persistence_failure_rolls_back():
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        def fail_dead_letter(_session, _context, _instances):
            if any(isinstance(item, DeadLetter) for item in db.new):
                raise RuntimeError("dead-letter persistence failed")

        event.listen(db, "before_flush", fail_dead_letter)
        try:
            with pytest.raises(RuntimeError, match="dead-letter persistence failed"):
                lifecycle.intake("broken.pdf", b"not-a-pdf")
        finally:
            event.remove(db, "before_flush", fail_dead_letter)

        assert db.query(DeadLetter).count() == 0


def test_gmail_tracking_failure_rolls_back_document_and_audit(invoice_pdf):
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)

        def fail_tracking(_session, _context, _instances):
            if any(isinstance(item, GmailAttachment) for item in db.new):
                raise RuntimeError("source tracking failed")

        event.listen(db, "before_flush", fail_tracking)
        try:
            with pytest.raises(RuntimeError, match="source tracking failed"):
                lifecycle.intake_gmail(
                    "invoice.pdf",
                    invoice_pdf,
                    GmailSource("message-atomic", "attachment-atomic"),
                )
        finally:
            event.remove(db, "before_flush", fail_tracking)

        assert db.query(Document).count() == 0
        assert db.query(AuditEvent).count() == 0
        assert db.query(GmailAttachment).count() == 0


def test_retry_failure_state_rolls_back_when_it_cannot_be_persisted():
    with SessionLocal() as db:
        lifecycle = DocumentIntakeLifecycle(db)
        with pytest.raises(ParseFailed):
            lifecycle.intake("broken.pdf", b"not-a-pdf")
        dead_letter_id = db.query(DeadLetter).one().id

        def fail_retry_update(_session, _context, _instances):
            if any(
                isinstance(item, DeadLetter) and item.retry_count == 1
                for item in db.dirty
            ):
                raise RuntimeError("retry update failed")

        event.listen(db, "before_flush", fail_retry_update)
        try:
            with pytest.raises(RuntimeError, match="retry update failed"):
                lifecycle.retry(dead_letter_id)
        finally:
            event.remove(db, "before_flush", fail_retry_update)

        assert db.get(DeadLetter, dead_letter_id).retry_count == 0

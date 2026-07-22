import base64
from email import message_from_bytes

from app.database import SessionLocal
from app.gmail import process_pdf_attachments, send_processing_summary


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeAttachments:
    def __init__(self, data):
        self.data = data

    def get(self, **_):
        return FakeRequest({"data": self.data})


class FakeMessages:
    def __init__(self, pdf_bytes):
        self.encoded = base64.urlsafe_b64encode(pdf_bytes).decode().rstrip("=")
        self.sent = []

    def list(self, **_):
        return FakeRequest({"messages": [{"id": "message-1"}]})

    def get(self, **_):
        return FakeRequest({
            "payload": {
                "parts": [{
                    "partId": "1",
                    "filename": "gmail-invoice.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "attachment-1"},
                }]
            }
        })

    def attachments(self):
        return FakeAttachments(self.encoded)

    def send(self, **kwargs):
        self.sent.append(kwargs["body"]["raw"])
        return FakeRequest({"id": "summary-message-1"})


class FakeGmail:
    def __init__(self, pdf_bytes):
        self.message_api = FakeMessages(pdf_bytes)

    def users(self):
        return self

    def messages(self):
        return self.message_api


def test_gmail_pdf_ingestion_is_idempotent(invoice_pdf):
    service = FakeGmail(invoice_pdf)
    with SessionLocal() as db:
        first = process_pdf_attachments(db, service, "has:attachment filename:pdf")
        second = process_pdf_attachments(db, service, "has:attachment filename:pdf")

    assert first == {
        "messages_scanned": 1,
        "attachments_seen": 1,
        "approved": 1,
        "review": 0,
        "duplicate": 0,
        "failed": 0,
        "skipped": 0,
    }
    assert second["skipped"] == 1
    assert second["approved"] == 0


def test_summary_email_contains_batch_counts(invoice_pdf):
    service = FakeGmail(invoice_pdf)
    summary = {
        "messages_scanned": 2,
        "attachments_seen": 3,
        "approved": 1,
        "review": 1,
        "duplicate": 1,
        "failed": 0,
        "skipped": 0,
    }

    message_id = send_processing_summary(service, "reviewer@example.test", summary)

    assert message_id == "summary-message-1"
    encoded = service.message_api.sent[0]
    message = message_from_bytes(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    assert message["To"] == "reviewer@example.test"
    assert message["Subject"] == "Ledgerline document processing summary"
    assert "Approved: 1" in message.get_payload()
    assert "Needs review: 1" in message.get_payload()

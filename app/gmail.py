"""Gmail OAuth, PDF attachment intake, and explicit summary-email delivery."""
from __future__ import annotations

import base64
from collections.abc import Iterator
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.document_lifecycle import (
    DocumentIntakeLifecycle,
    GmailSource,
    SourceAlreadyProcessed,
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def authorize(client_file: Path, token_file: Path) -> Credentials:
    if not client_file.is_file():
        raise FileNotFoundError(f"OAuth client file not found: {client_file}")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    credentials = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def load_credentials(token_file: Path) -> Credentials:
    if not token_file.is_file():
        raise FileNotFoundError("Gmail is not authorized. Run scripts/gmail_auth.py first.")
    credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        token_file.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials.valid:
        raise RuntimeError("Stored Gmail authorization is invalid; authorize again.")
    return credentials


def build_gmail_service(token_file: Path):
    return build("gmail", "v1", credentials=load_credentials(token_file), cache_discovery=False)


def process_pdf_attachments(db: Session, service, query: str) -> dict[str, int]:
    lifecycle = DocumentIntakeLifecycle(db)
    summary = {
        "messages_scanned": 0,
        "attachments_seen": 0,
        "approved": 0,
        "review": 0,
        "duplicate": 0,
        "failed": 0,
        "skipped": 0,
    }
    for message_id in _message_ids(service, query):
        summary["messages_scanned"] += 1
        message = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        for part in _pdf_parts(message.get("payload", {})):
            summary["attachments_seen"] += 1
            attachment_id = part.get("body", {}).get("attachmentId") or f"inline:{part.get('partId', '')}"
            source = GmailSource(message_id, attachment_id)
            if lifecycle.gmail_source_result(source):
                summary["skipped"] += 1
                continue
            try:
                data = _attachment_bytes(service, message_id, part)
            except Exception as exc:
                repeated = lifecycle.record_gmail_failure(
                    source,
                    part.get("filename", "attachment.pdf"),
                    str(exc),
                )
                if isinstance(repeated, SourceAlreadyProcessed):
                    summary["skipped"] += 1
                    continue
                summary["failed"] += 1
                continue
            try:
                result = lifecycle.intake_gmail(part["filename"], data, source)
                if isinstance(result, SourceAlreadyProcessed):
                    summary["skipped"] += 1
                else:
                    summary[result.status.value] += 1
            except Exception:
                summary["failed"] += 1
    return summary


def send_processing_summary(service, recipient: str, summary: dict[str, int]) -> str:
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = "Ledgerline document processing summary"
    message.set_content(_summary_text(summary))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return result["id"]


def _message_ids(service, query: str) -> Iterator[str]:
    page_token = None
    while True:
        response = service.users().messages().list(
            userId="me", q=query, pageToken=page_token
        ).execute()
        yield from (message["id"] for message in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break


def _pdf_parts(payload: dict) -> Iterator[dict]:
    if payload.get("filename", "").lower().endswith(".pdf"):
        yield payload
    for part in payload.get("parts", []):
        yield from _pdf_parts(part)


def _attachment_bytes(service, message_id: str, part: dict) -> bytes:
    body = part.get("body", {})
    encoded = body.get("data")
    if not encoded and body.get("attachmentId"):
        response = service.users().messages().attachments().get(
            userId="me", messageId=message_id, id=body["attachmentId"]
        ).execute()
        encoded = response.get("data")
    if not encoded:
        raise ValueError("Gmail attachment has no data")
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))


def _summary_text(summary: dict[str, int]) -> str:
    return "\n".join([
        "Ledgerline finished processing Gmail PDF attachments.",
        "",
        f"Messages scanned: {summary['messages_scanned']}",
        f"Attachments found: {summary['attachments_seen']}",
        f"Approved: {summary['approved']}",
        f"Needs review: {summary['review']}",
        f"Duplicates: {summary['duplicate']}",
        f"Failed: {summary['failed']}",
        f"Previously processed: {summary['skipped']}",
    ])

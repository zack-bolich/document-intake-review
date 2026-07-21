"""Approved-record export services with no credentials stored in source control."""
from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from app.models import Document

EXPORT_HEADERS = [
    "record_id", "document_type", "document_number", "vendor", "amount",
    "currency", "document_date", "confidence", "approved_at",
]


def document_row(document: Document) -> list[str]:
    return [
        document.id,
        document.document_type,
        document.document_number or "",
        document.vendor or "",
        f"{document.amount:.2f}" if document.amount is not None else "",
        document.currency or "",
        document.document_date.isoformat() if document.document_date else "",
        f"{document.confidence:.4f}",
        document.approved_at.isoformat() if document.approved_at else "",
    ]


def approved_csv(documents: Sequence[Document]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(EXPORT_HEADERS)
    writer.writerows(document_row(document) for document in documents)
    return output.getvalue()


def append_to_google_sheet(
    documents: Sequence[Document],
    *,
    credentials_file: Path,
    spreadsheet_id: str,
    range_name: str,
) -> int:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        str(credentials_file),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    values_api = service.spreadsheets().values()
    existing = values_api.get(
        spreadsheetId=spreadsheet_id,
        range=_header_range(range_name),
    ).execute()
    rows = [document_row(document) for document in documents]
    if not existing.get("values"):
        rows.insert(0, EXPORT_HEADERS)
    if not rows:
        return 0
    values_api.append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return len(documents)


def _header_range(range_name: str) -> str:
    sheet = range_name.split("!", 1)[0] if "!" in range_name else "Sheet1"
    return f"{sheet}!A1:I1"

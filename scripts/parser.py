"""Simple parser that extracts common fields from receipt/invoice text."""

from __future__ import annotations

import json
import re


FIELD_PATTERNS = [
    ("document_number", re.compile(r"\b(?:invoice|receipt|ref(?:erence)?|id)\s*(?:number|no|#)?\s*[:\-]?\s*([A-Za-z0-9\-]+)", re.IGNORECASE)),
    ("vendor", re.compile(r"\b(?:vendor|merchant|from|sold\s+by)\s*[:\-]?\s*(.+)", re.IGNORECASE)),
    ("amount", re.compile(r"\b(?:total|amount|due)\s*[:\-]?\s*\$?\s*([0-9]+(?:\.[0-9]{2})?)", re.IGNORECASE)),
    ("currency", re.compile(r"\b(?:currency|curr)\s*[:\-]?\s*([A-Z]{3})\b", re.IGNORECASE)),
    ("date", re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")),
]


def extract_fields(raw_text: str) -> dict:
    text = raw_text.strip()
    output: dict = {
        "document_number": "",
        "vendor": "",
        "amount": "",
        "currency": "USD",
        "date": "",
    }
    for key, pattern in FIELD_PATTERNS:
        match = pattern.search(text)
        if match:
            output[key] = match.group(1).strip()
    return output


def parse_text(raw_text: str) -> tuple[dict, list[str]]:
    fields = extract_fields(raw_text)
    issues: list[str] = []

    if not fields["vendor"]:
        issues.append("missing_vendor")
    if not fields["amount"]:
        issues.append("missing_amount")
    else:
        try:
            float(fields["amount"])
        except ValueError:
            issues.append("invalid_amount")

    if not fields["date"]:
        issues.append("missing_date")

    if not fields["document_number"]:
        issues.append("missing_document_number")

    if not fields["currency"]:
        fields["currency"] = "USD"

    return fields, issues


def parse_file_bytes(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".json"):
        return _parse_json_text(data)
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _parse_json_text(data: bytes) -> str:
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    # flatten JSON to readable fields
    lines = []
    if payload.get("vendor"):
        lines.append(f"vendor {payload['vendor']}")
    if payload.get("doc_type"):
        lines.append(f"invoice {payload['doc_type']}")
    if payload.get("document_number"):
        lines.append(f"invoice number {payload['document_number']}")
    if payload.get("amount"):
        lines.append(f"amount {payload['amount']}")
    if payload.get("currency"):
        lines.append(f"currency {payload['currency']}")
    if payload.get("date"):
        lines.append(f"{payload['date']}")
    return "\n".join(lines)


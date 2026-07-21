"""Deterministic parsing. An LLM fallback may be added later behind a low-confidence gate."""
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import fitz


PATTERNS = {
    "document_number": re.compile(r"(?:invoice\s*(?:number|no\.?|#)|receipt\s*(?:number|no\.?|#)?|reference)\s*[:#-]?\s*([A-Z0-9-]+)", re.I),
    "vendor": re.compile(r"(?:vendor|merchant|sold\s+by|from)\s*[:#-]\s*([^\r\n]+)", re.I),
    "amount": re.compile(r"(?:grand\s+total|total|amount\s+due|amount)\s*[:#-]?\s*(?:USD\s*)?\$?\s*([0-9,]+(?:\.\d{2})?)", re.I),
    "currency": re.compile(r"(?:currency|curr)\s*[:#-]?\s*([A-Z]{3})\b", re.I),
    "date": re.compile(r"(?:date\s*[:#-]?\s*)?(\d{4}-\d{2}-\d{2})", re.I),
}


@dataclass(frozen=True)
class ParseResult:
    fields: dict
    field_confidence: dict[str, float]
    confidence: float
    issues: list[str]
    raw_text: str


def extract_text(filename: str, data: bytes) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            return "\n".join(page.get_text("text") for page in pdf).strip()
    if suffix == "json":
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON document must be an object")
        labels = {
            "doc_type": "Document Type", "document_number": "Invoice Number",
            "vendor": "Vendor", "date": "Date", "amount": "Amount", "currency": "Currency",
        }
        return "\n".join(f"{labels[k]}: {v}" for k, v in payload.items() if k in labels and v is not None)
    return data.decode("utf-8")


def parse_document(filename: str, data: bytes) -> ParseResult:
    text = extract_text(filename, data).strip()
    if not text:
        raise ValueError("no extractable text")
    values: dict = {}
    scores: dict[str, float] = {}
    for name, pattern in PATTERNS.items():
        match = pattern.search(text)
        values[name] = match.group(1).strip() if match else None
        scores[name] = 0.98 if match else 0.0

    lower = text.lower()
    if "invoice" in lower:
        values["document_type"] = "invoice"
    elif "receipt" in lower or "merchant" in lower:
        values["document_type"] = "receipt"
    else:
        values["document_type"] = "unknown"
    scores["document_type"] = 0.95 if values["document_type"] != "unknown" else 0.2

    issues = []
    try:
        values["amount"] = Decimal(values["amount"].replace(",", "")) if values["amount"] else None
    except InvalidOperation:
        values["amount"] = None
        scores["amount"] = 0.0
        issues.append("invalid_amount")
    raw_date = values.pop("date")
    try:
        values["document_date"] = date.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        values.pop("date", None)
        values["document_date"] = None
        scores["date"] = 0.0
        issues.append("invalid_date")
    scores["document_date"] = scores.pop("date")
    values["currency"] = (values["currency"] or "USD").upper()
    scores["currency"] = scores["currency"] or 0.75
    for name in ("vendor", "amount", "document_date", "document_number"):
        if values.get(name) is None:
            issues.append(f"missing_{name}")
    confidence = round(sum(scores.values()) / len(scores), 4)
    return ParseResult(values, scores, confidence, issues, text)

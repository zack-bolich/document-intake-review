"""Deterministic parsing. An LLM fallback may be added later behind a low-confidence gate."""
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import fitz


PATTERNS = {
    "document_number": re.compile(r"(?:invoice[ \t]*(?:number|no\.?|#)?|receipt[ \t]*(?:number|no\.?|#)?|reference)[ \t]*[:#-]?[ \t]*([A-Z0-9-]+)", re.I),
    "vendor": re.compile(r"(?:vendor|merchant|sold\s+by|from)\s*[:#-]\s*([^\r\n]+)", re.I),
    "amount": re.compile(
        r"(?<!sub)(?:grand\s+total|total\s+due|total|amount\s+due|amount)"
        r"(?:\s*\([A-Z]{3}\))?\s*[:#-]?\s*(?:[A-Z]{3}\s*)?\$?\s*"
        r"([0-9,]+(?:\.\d{2})?)",
        re.I,
    ),
    "currency": re.compile(
        r"(?:currency|curr)\s*[:#-]?\s*([A-Z]{3})\b|"
        r"(?:total(?:\s+due)?)\s*\(([A-Z]{3})\)",
        re.I,
    ),
    "date": re.compile(
        r"(?:issue\s+date|invoice\s+date|date)\s*[:#-]?\s*"
        r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})",
        re.I,
    ),
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
        matches = list(pattern.finditer(text))
        match = matches[-1] if name == "amount" and matches else (matches[0] if matches else None)
        values[name] = next(
            (group.strip() for group in match.groups() if group),
            None,
        ) if match else None
        scores[name] = 0.98 if match else 0.0

    if not values["vendor"]:
        values["vendor"] = _infer_vendor(text)
        scores["vendor"] = 0.85 if values["vendor"] else 0.0

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
        values["document_date"] = _parse_date(raw_date) if raw_date else None
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


def _parse_date(value: str) -> date:
    if "-" in value:
        return date.fromisoformat(value)
    day, month, year = (int(part) for part in value.split("/"))
    return date(year, month, day)


def _infer_vendor(text: str) -> str | None:
    """Use the first heading before BILL TO when no explicit vendor label exists."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    boundary = next(
        (index for index, line in enumerate(lines) if line.upper() == "BILL TO"),
        min(len(lines), 5),
    )
    ignored = re.compile(r"^(?:invoice|receipt|tax\s+invoice)(?:\s+[A-Z0-9-]+)?$", re.I)
    return next(
        (line for line in lines[:boundary] if not ignored.fullmatch(line)),
        None,
    )

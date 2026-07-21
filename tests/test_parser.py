from decimal import Decimal

from app.parser import parse_document


def test_extracts_structured_invoice_pdf(invoice_pdf):
    result = parse_document("invoice.pdf", invoice_pdf)
    assert result.fields["document_number"] == "INV-3001"
    assert result.fields["vendor"] == "Northstar Office Supply"
    assert result.fields["amount"] == Decimal("1245.50")
    assert result.fields["document_type"] == "invoice"
    assert result.confidence >= 0.9
    assert result.issues == []


def test_preserves_json_document_number_regression():
    data = b'{"doc_type":"invoice","document_number":"INV-1002","vendor":"Bluewater Logistics","date":"2026-07-01","amount":"900.00","currency":"USD"}'
    result = parse_document("invoice.json", data)
    assert result.fields["document_number"] == "INV-1002"


def test_missing_fields_are_low_confidence():
    result = parse_document("note.txt", b"INVOICE\nVendor: Synthetic Vendor")
    assert "missing_amount" in result.issues
    assert result.confidence < 0.85


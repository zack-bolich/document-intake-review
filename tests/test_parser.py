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


def test_extracts_receipt_number_without_crossing_line_boundary(receipt_pdf):
    result = parse_document("receipt.pdf", receipt_pdf)
    assert result.fields["document_number"] == "RCP-2002"
    assert result.fields["vendor"] == "Synthetic Corner Cafe"
    assert result.fields["document_type"] == "receipt"


def test_preserves_json_document_number_regression():
    data = b'{"doc_type":"invoice","document_number":"INV-1002","vendor":"Bluewater Logistics","date":"2026-07-01","amount":"900.00","currency":"USD"}'
    result = parse_document("invoice.json", data)
    assert result.fields["document_number"] == "INV-1002"


def test_missing_fields_are_low_confidence():
    result = parse_document("note.txt", b"INVOICE\nVendor: Synthetic Vendor")
    assert "missing_amount" in result.issues
    assert result.confidence < 0.85


def test_australian_invoice_uses_total_not_subtotal():
    text = b"""Your Business Name
BILL TO
Invoice 2022435
Your Client
Tax invoice
Issue date: 19/7/2022
Due date: 3/8/2022
Reference: 2022435
Total due (AUD)
$2,510.00
Subtotal:
$2,100.00
Total (AUD):
$2,510.00
"""

    result = parse_document("invoice.txt", text)

    assert result.fields["document_number"] == "2022435"
    assert result.fields["vendor"] == "Your Business Name"
    assert result.fields["amount"] == Decimal("2510.00")
    assert result.fields["currency"] == "AUD"
    assert result.fields["document_date"].isoformat() == "2022-07-19"
    assert result.issues == []


def test_amount_and_currency_come_from_final_total_not_subtotal():
    text = b"""Invoice
Vendor: Synthetic Exporter
Invoice Number: INV-NZD-1
Sub Total (AUD): 10.00
Total (NZD): 20.00
Date: 2026-07-20
"""

    result = parse_document("multi-currency.txt", text)

    assert result.fields["amount"] == Decimal("20.00")
    assert result.fields["currency"] == "NZD"
    assert result.issues == []


def test_one_decimal_amount_is_parsed_without_truncation():
    text = b"""Invoice
Vendor: Synthetic Supply
Invoice Number: INV-DECIMAL-1
Total: $1,245.5
Date: 2026-07-20
"""

    result = parse_document("one-decimal.txt", text)

    assert result.fields["amount"] == Decimal("1245.5")
    assert result.issues == []


def test_more_than_two_decimal_places_requires_review():
    text = b"""Invoice
Vendor: Synthetic Supply
Invoice Number: INV-PRECISION-1
Total: $1,245.503
Date: 2026-07-20
"""

    result = parse_document("three-decimals.txt", text)

    assert result.fields["amount"] is None
    assert "invalid_amount_precision" in result.issues
    assert "missing_amount" in result.issues

"""Generate fictional, deterministic portfolio fixtures. No real customer data."""
from pathlib import Path

import fitz


FIXTURES = {
    "invoice_3001.pdf": "INVOICE\nVendor: Northstar Office Supply\nInvoice Number: INV-3001\nDate: 2026-07-15\nAmount Due: $1,245.50\nCurrency: USD",
    "receipt_2002.pdf": "RECEIPT\nMerchant: Synthetic Corner Cafe\nReceipt: RCP-2002\nDate: 2026-07-16\nTotal: $24.75\nCurrency: USD",
    "invoice_needs_review.pdf": "INVOICE\nVendor: Fictional Repair Works\nInvoice Number: INV-REVIEW-1",
}


def main() -> None:
    destination = Path("sample-data/synthetic-pdfs")
    destination.mkdir(parents=True, exist_ok=True)
    for filename, text in FIXTURES.items():
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_textbox(fitz.Rect(72, 72, 540, 720), text, fontsize=11)
        pdf.save(destination / filename)
        pdf.close()


if __name__ == "__main__":
    main()

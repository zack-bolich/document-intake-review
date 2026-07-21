import os
os.environ["DATABASE_URL"] = "sqlite:///./test_document_intake.db"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_pdf(text: str) -> bytes:
    import fitz
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox(fitz.Rect(72, 72, 540, 720), text, fontsize=11)
    data = pdf.tobytes()
    pdf.close()
    return data


@pytest.fixture
def invoice_pdf():
    return make_pdf("INVOICE\nVendor: Northstar Office Supply\nInvoice Number: INV-3001\nDate: 2026-07-15\nAmount Due: $1,245.50\nCurrency: USD")


@pytest.fixture
def receipt_pdf():
    return make_pdf("RECEIPT\nMerchant: Synthetic Corner Cafe\nReceipt: RCP-2002\nDate: 2026-07-16\nTotal: $24.75\nCurrency: USD")

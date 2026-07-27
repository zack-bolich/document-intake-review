def upload(client, name, content, media_type="application/pdf"):
    return client.post("/api/v1/documents", files={"file": (name, content, media_type)})


def test_ingest_approved_invoice_and_audit(client, invoice_pdf):
    response = upload(client, "invoice.pdf", invoice_pdf)
    assert response.status_code == 201
    record = response.json()
    assert record["status"] == "approved"
    assert record["document_number"] == "INV-3001"
    audit = client.get(f"/api/v1/documents/{record['id']}/audit")
    assert [event["action"] for event in audit.json()] == ["ingested"]


def test_duplicate_is_detected_and_linked(client, invoice_pdf):
    first = upload(client, "first.pdf", invoice_pdf).json()
    second = upload(client, "copy.pdf", invoice_pdf).json()
    assert second["status"] == "duplicate"
    assert second["duplicate_of_id"] == first["id"]


def test_missing_vendor_does_not_poison_business_duplicate_detection(client):
    missing_vendor = b"""Invoice
BILL TO
Invoice Number: INV-1001
Amount: 10.00
Date: 2026-07-20
"""
    different_vendor = b"""Invoice
Invoice Number: INV-1001
Vendor: Other Company
Amount: 99.00
Date: 2026-07-21
"""

    first = upload(client, "vendor-missing.txt", missing_vendor, "text/plain").json()
    second = upload(client, "different-vendor.txt", different_vendor, "text/plain").json()

    assert first["vendor"] is None
    assert first["status"] == "review"
    assert second["vendor"] == "Other Company"
    assert second["status"] == "approved"
    assert second["duplicate_of_id"] is None


def test_same_vendor_and_number_are_a_business_duplicate(client):
    first_data = b"""Invoice
Invoice Number: INV-2001
Vendor: Synthetic Supply
Amount: 10.00
Date: 2026-07-20
"""
    changed_data = b"""Invoice
Invoice Number: INV-2001
Vendor: Synthetic Supply
Amount: 11.00
Date: 2026-07-21
"""

    first = upload(client, "first.txt", first_data, "text/plain").json()
    second = upload(client, "changed.txt", changed_data, "text/plain").json()

    assert second["status"] == "duplicate"
    assert second["duplicate_of_id"] == first["id"]


def test_review_correction_and_approval(client):
    partial = b"INVOICE\nVendor: Synthetic Repairs\nInvoice Number: INV-LOW-1"
    record = upload(client, "partial.txt", partial, "text/plain").json()
    assert record["status"] == "review"
    queue = client.get("/api/v1/documents", params={"status": "review"}).json()
    assert [item["id"] for item in queue] == [record["id"]]
    corrected = client.patch(f"/api/v1/documents/{record['id']}", json={"amount": "87.20", "currency": "USD", "document_date": "2026-07-17", "actor": "portfolio-reviewer"})
    assert corrected.status_code == 200
    approved = client.post(f"/api/v1/documents/{record['id']}/approve", json={"actor": "portfolio-reviewer"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    actions = [item["action"] for item in client.get(f"/api/v1/documents/{record['id']}/audit").json()]
    assert actions == ["ingested", "corrected", "approved"]


def test_unreadable_document_goes_to_dead_letter(client):
    response = upload(client, "empty.pdf", b"not-a-pdf")
    assert response.status_code == 422
    dead_letters = client.get("/api/v1/dead-letters").json()
    assert len(dead_letters) == 1
    assert dead_letters[0]["filename"] == "empty.pdf"
    retry = client.post(f"/api/v1/dead-letters/{dead_letters[0]['id']}/retry")
    assert retry.status_code == 422
    assert client.get("/api/v1/dead-letters").json()[0]["retry_count"] == 1


def test_openapi_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert "/api/v1/documents" in client.get("/openapi.json").json()["paths"]


def test_frontend_origin_is_allowed(client):
    response = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

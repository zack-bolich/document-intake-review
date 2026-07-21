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

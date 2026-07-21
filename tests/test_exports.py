import csv
import io

from app.config import get_settings


def upload(client, name, content):
    return client.post(
        "/api/v1/documents",
        files={"file": (name, content, "application/pdf")},
    )


def test_csv_download_contains_only_approved_records(client, invoice_pdf):
    approved = upload(client, "approved.pdf", invoice_pdf).json()
    client.post(
        "/api/v1/documents",
        files={"file": ("review.txt", b"INVOICE\nVendor: Fictional Vendor", "text/plain")},
    )

    response = client.get("/api/v1/exports/approved.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "approved-records.csv" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["record_id"] == approved["id"]
    assert rows[0]["document_number"] == "INV-3001"
    actions = [
        event["action"]
        for event in client.get(f"/api/v1/documents/{approved['id']}/audit").json()
    ]
    assert actions == ["ingested", "exported_csv"]


def test_google_sheets_requires_configuration(client):
    response = client.post("/api/v1/exports/google-sheets")
    assert response.status_code == 503
    assert response.json()["detail"] == "Google Sheets export is not configured"


def test_google_sheets_exports_each_approved_record_once(
    client, invoice_pdf, tmp_path, monkeypatch
):
    record = upload(client, "approved.pdf", invoice_pdf).json()
    credentials = tmp_path / "service-account.json"
    credentials.write_text("{}", encoding="utf-8")
    settings = get_settings()
    monkeypatch.setattr(settings, "google_sheets_credentials_file", credentials)
    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "synthetic-sheet-id")
    calls = []

    def fake_append(documents, **kwargs):
        calls.append((documents, kwargs))
        return len(documents)

    monkeypatch.setattr("app.api.append_to_google_sheet", fake_append)

    first = client.post("/api/v1/exports/google-sheets")
    second = client.post("/api/v1/exports/google-sheets")

    assert first.status_code == 200
    assert first.json()["exported_count"] == 1
    assert second.json()["exported_count"] == 0
    assert second.json()["skipped_count"] == 1
    assert len(calls) == 1
    actions = [
        event["action"]
        for event in client.get(f"/api/v1/documents/{record['id']}/audit").json()
    ]
    assert "exported_google_sheets" in actions

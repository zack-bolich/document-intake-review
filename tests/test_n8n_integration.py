import json
from pathlib import Path

import pytest

from app.config import get_settings

ENDPOINT = "/api/v1/integrations/n8n/documents"
HEADERS = {"X-Ledgerline-Key": "test-n8n-key"}


@pytest.fixture(autouse=True)
def restore_n8n_settings():
    settings = get_settings()
    original_key = settings.n8n_api_key
    original_limit = settings.max_upload_bytes
    yield
    settings.n8n_api_key = original_key
    settings.max_upload_bytes = original_limit


def post_file(client, name, content, media_type="application/pdf", headers=HEADERS):
    return client.post(ENDPOINT, headers=headers, files={"file": (name, content, media_type)})


def test_n8n_endpoint_fails_closed_when_unconfigured(client, invoice_pdf):
    get_settings().n8n_api_key = None
    response = post_file(client, "invoice.pdf", invoice_pdf)
    assert response.status_code == 503


def test_n8n_endpoint_rejects_missing_and_invalid_keys(client, invoice_pdf):
    get_settings().n8n_api_key = "test-n8n-key"
    assert post_file(client, "invoice.pdf", invoice_pdf, headers={}).status_code == 401
    response = post_file(
        client,
        "invoice.pdf",
        invoice_pdf,
        headers={"X-Ledgerline-Key": "wrong"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"


def test_n8n_endpoint_ingests_and_audits_with_valid_key(client, invoice_pdf):
    get_settings().n8n_api_key = "test-n8n-key"
    response = post_file(client, "invoice.pdf", invoice_pdf)
    assert response.status_code == 201
    record = response.json()
    assert record["status"] == "approved"
    audit = client.get(f"/api/v1/documents/{record['id']}/audit")
    assert [event["action"] for event in audit.json()] == ["ingested"]


def test_n8n_endpoint_uses_authoritative_duplicate_detection(client, invoice_pdf):
    get_settings().n8n_api_key = "test-n8n-key"
    first = post_file(client, "first.pdf", invoice_pdf).json()
    duplicate = post_file(client, "copy.pdf", invoice_pdf).json()
    assert duplicate["status"] == "duplicate"
    assert duplicate["duplicate_of_id"] == first["id"]


def test_n8n_endpoint_matches_upload_validation(client):
    settings = get_settings()
    settings.n8n_api_key = "test-n8n-key"
    assert post_file(client, "image.png", b"png", "image/png").status_code == 415

    original_limit = settings.max_upload_bytes
    settings.max_upload_bytes = 4
    try:
        assert post_file(client, "large.txt", b"12345", "text/plain").status_code == 413
    finally:
        settings.max_upload_bytes = original_limit

    response = post_file(client, "broken.pdf", b"not-a-pdf")
    assert response.status_code == 422
    assert client.get("/api/v1/dead-letters").json()[0]["filename"] == "broken.pdf"


def test_exported_workflow_is_credential_free_and_preserves_boundaries():
    workflow_path = Path("n8n/workflows/ledgerline-document-intake.json")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    serialized = json.dumps(workflow)
    nodes = workflow["nodes"]
    names = {node["name"] for node in nodes}

    assert workflow["active"] is False
    assert "credentials" not in serialized
    assert "instanceId" not in serialized
    assert "webhookId" not in serialized
    assert "seenDocumentIds" not in serialized
    assert "X-Ledgerline-Key" in serialized
    assert "$env" not in serialized
    assert "$vars.LEDGERLINE_OPERATOR_EMAIL" in serialized
    assert serialized.count('"genericAuthType": "httpHeaderAuth"') == 3
    assert "http://api:8000/api/v1/integrations/n8n/documents" in serialized
    assert {"Internal Upload Form", "Gmail Attachment Trigger", "Route Ledgerline Status"} <= names

    waits = sorted(
        node["parameters"]["amount"]
        for node in nodes
        if node["type"] == "n8n-nodes-base.wait"
    )
    assert waits == [2, 4]

    email_sources = {
        connection["node"]
        for source in ("Review Required", "Terminal Failure")
        for branch in workflow["connections"][source]["main"]
        for connection in branch
    }
    assert email_sources == {"Email Operator"}

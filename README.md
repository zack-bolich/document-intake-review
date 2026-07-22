# Document Intake and Review Automation

A full-stack portfolio application that ingests **synthetic** invoice and receipt PDFs, extracts validated fields with deterministic rules, scores confidence, detects duplicates, and routes uncertain records through a polished human review dashboard.

The tested backend now has a React dashboard. Live Google/Gmail credentials remain deliberately deferred; Sheets export, Gmail ingestion, summary email, and the optional n8n webhook are the next integration milestone.

## Implemented

- FastAPI and Pydantic API with interactive OpenAPI documentation
- React, TypeScript, and Vite review dashboard
- upload, status filters, confidence visualization, corrections, approvals, audit history, and dead-letter retry UI
- approved-record CSV download and idempotent Google Sheets export
- SQLAlchemy models supporting SQLite locally and PostgreSQL in Docker
- deterministic PyMuPDF extraction for PDF, plus TXT and JSON compatibility
- field-level and aggregate confidence scores
- content-hash and business-key duplicate detection
- review queue, corrections, approval rules, timestamps, and audit history
- durable database dead letters for unreadable documents
- retry counts and a dead-letter retry endpoint
- Pytest, Ruff, GitHub Actions, Dockerfile, and Docker Compose

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs). SQLite creates `document_intake.db` automatically.

In a second terminal, run the dashboard:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend expects the API at `http://127.0.0.1:8000/api/v1`; override it with `VITE_API_URL` in `frontend/.env.local` when needed.

```powershell
ruff check app tests
pytest --cov=app --cov-report=term-missing
```

For the complete React + FastAPI + PostgreSQL stack: `docker compose up --build`, then open [http://localhost:5173](http://localhost:5173).

Regenerate the fictional PDF fixtures with `python scripts/generate_synthetic_pdfs.py`.

## API workflow

1. `POST /api/v1/documents` with a synthetic PDF, TXT, or JSON file.
2. Inspect `confidence`, `field_confidence`, `status`, and `duplicate_of_id`.
3. `GET /api/v1/documents?status=review` for the review queue.
4. `PATCH /api/v1/documents/{id}` to correct fields.
5. `POST /api/v1/documents/{id}/approve` to approve a complete, non-duplicate record.
6. `GET /api/v1/documents/{id}/audit` for event history.
7. `GET /api/v1/dead-letters` for extraction failures.
8. `GET /api/v1/exports/approved.csv` to download approved records.
9. `POST /api/v1/exports/google-sheets` to append approvals not previously exported.

## Google Sheets setup (optional)

CSV export requires no credentials. To enable Google Sheets locally:

1. Create a Google Cloud project and enable the Google Sheets API.
2. Create a service account and download its JSON key.
3. Save the key as `credentials/service-account.json`. The entire `credentials/` directory is ignored by Git.
4. Create a spreadsheet with a tab named `Approved Records`.
5. Share that spreadsheet with the service account's `client_email` as an editor.
6. Copy `.env.example` to `.env` and set:

```dotenv
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials/service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=the_id_between_d_and_edit_in_the_sheet_url
GOOGLE_SHEETS_RANGE=Approved Records!A:I
```

Restart FastAPI after changing `.env`. The exporter creates the header row when needed and uses audit events to avoid appending the same approved record twice. See Google's official [Sheets values guide](https://developers.google.com/workspace/sheets/api/guides/values) for the underlying append behavior.

## Gmail attachment intake (optional)

Gmail access is local and opt-in. No mailbox credentials or tokens belong in Git.

1. Enable the Gmail API, configure an External OAuth app in Testing, and add your Gmail address as a test user.
2. Create a Desktop app OAuth client and save it as `credentials/gmail-client.json`.
3. Authorize once:

```powershell
python scripts/gmail_auth.py
```

Google opens a consent page. After approval, the ignored `credentials/gmail-token.json` file stores the refresh token.

4. Process matching PDF attachments without sending email:

```powershell
python scripts/process_gmail.py
```

The default search is `has:attachment filename:pdf newer_than:30d`. Each Gmail message/attachment pair is tracked, so later runs skip it.

5. To send the summary, set your recipient in `.env`:

```dotenv
GMAIL_SUMMARY_RECIPIENT=your-address@example.com
```

Then explicitly request sending:

```powershell
python scripts/process_gmail.py --send-summary
```

OAuth scopes are limited to `gmail.readonly` and `gmail.send`. See Google's official [Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) and [sending guide](https://developers.google.com/workspace/gmail/api/guides/sending).

## Confidence and privacy

Each recognized field receives a deterministic confidence score; the aggregate is their mean. Missing required fields or a score below `REVIEW_THRESHOLD` routes the record to review. A future LLM fallback may run only behind this low-confidence boundary; none is enabled now.

All fixtures and names are fictional. `.env.example` contains configuration only. Live OAuth integrations will use environment-injected secrets in a later milestone.

## Roadmap

- retry endpoint and scheduled retry policy
- optional signed n8n webhook
- optional low-confidence LLM extraction with provenance

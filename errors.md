# Operations and Recovery

Ledgerline records uncertain documents in the review queue and extraction failures in
the database-backed dead-letter queue. The FastAPI service is the only supported
processing path.

## API or dashboard is unavailable

1. Confirm the API responds at `http://localhost:8000/health`.
2. Confirm the dashboard is using `http://127.0.0.1:8000/api/v1`, or set
   `VITE_API_URL` in `frontend/.env.local`.
3. When using Docker, run `docker compose ps` and inspect `docker compose logs api`.
4. From a local checkout, start the API with `uvicorn app.main:app --reload`.

## A document enters review

This is expected when required fields are missing, a value fails validation, or the
aggregate confidence is below `REVIEW_THRESHOLD`.

1. Open the record in the dashboard.
2. Inspect the field-level confidence values.
3. Correct the missing or uncertain fields.
4. Approve the complete record.
5. Confirm the correction and approval events appear in audit history.

Do not weaken validation to force an uncertain document into the approved state.
Add a synthetic regression fixture and parser test when supporting a new layout.

## Extraction fails

Unreadable, malformed, or image-only PDFs are stored in the dead-letter queue.

1. Inspect `GET /api/v1/dead-letters` or the dashboard failure panel.
2. Review the stored error without exposing the document payload in logs.
3. Use `POST /api/v1/dead-letters/{id}/retry` after correcting the parser or fixture.
4. Confirm `retry_count`, `updated_at`, and the final document status.

## A document is marked duplicate

Ledgerline detects byte-identical files by SHA-256 content hash and business
duplicates by document number plus a non-empty matching vendor.

1. Inspect `duplicate_of_id`.
2. Confirm the original record is the intended match.
3. For unexpected matches, reproduce the case with synthetic data and add a
   regression test before changing the duplicate rules.

## Google Sheets export is unavailable

CSV export requires no credentials and remains the fallback.

1. Confirm the configured service-account file exists outside version control.
2. Confirm `GOOGLE_SHEETS_SPREADSHEET_ID` and `GOOGLE_SHEETS_RANGE`.
3. Confirm the spreadsheet is shared with the service-account email.
4. Restart the API after changing `.env`.

## Gmail processing fails

1. Run `python scripts/gmail_auth.py` if the local OAuth token is absent or invalid.
2. Confirm `credentials/gmail-client.json` and `credentials/gmail-token.json` remain
   ignored by Git.
3. Run `python scripts/process_gmail.py` without `--send-summary` first.
4. Add `--send-summary` only after `GMAIL_SUMMARY_RECIPIENT` is configured.

## Verification checklist

```powershell
python -m ruff check app tests scripts/gmail_auth.py scripts/process_gmail.py scripts/generate_synthetic_pdfs.py
python -m pytest --cov=app --cov-report=term-missing
npm test --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
docker compose config --quiet
```

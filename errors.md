# Runbook / Maintenance

## Severity 1: No files are processed
### Symptoms
- `python scripts/process_documents.py --run-once` prints no processed files
### Cause
- `INPUT_DIR` points to wrong path
- Empty or missing folder
### Recovery
1. Confirm `.env` values
2. Confirm `sample-data/inbox` exists
3. Run once with defaults after moving out of nested folder

## Severity 2: Most files go to dead-letter
### Symptoms
- `results/dead_letter.csv` grows quickly
### Cause
- Missing required fields: vendor, date, amount, document number
### Recovery
1. Update sample document format to match parser regex
2. Add regex rules in `scripts/parser.py`
3. Optionally prefill missing fields in parser fallback map

## Severity 3: Same file processed repeatedly
### Symptoms
- duplicate rows in clean output
### Cause
- `state/processed.json` is missing or deleted
### Recovery
1. Keep `state/` under version control only as `.gitignore` example
2. Restore prior manifest or accept clean reset
3. Add unique invoice/receipt IDs upstream

## Severity 4: Script crashes on first run
### Symptoms
- Import or file encoding errors
### Cause
- Missing dependency
### Recovery
1. Activate venv
2. `pip install -r requirements.txt`
3. Re-run

## Recovery checklist
- keep expected output updated
- test one new doc format per change
- document any parser edits in this file

# Ledgerline agent contract

These instructions apply to every coding agent working in this repository.

## Before editing

1. Read the assigned GitHub issue and restate its acceptance criteria.
2. Run `git status --short --branch`. Do not overwrite or discard existing changes.
3. Work only on a dedicated branch named `agent/<agent>/<issue>-<slug>`.
4. Confirm the files you own for the task. If another active task owns a file you need,
   stop and coordinate through the issue instead of editing it concurrently.

Valid agent names are `codex`, `codex-cloud`, `claude`, and `devin`.

## Repository map

- `app/`: FastAPI API, services, parsing, persistence, Gmail, and exports
- `frontend/src/`: React dashboard and frontend API/types
- `tests/`: backend tests
- `tests/e2e/`: Playwright API, UI, and accessibility tests
- `scripts/`: local Gmail and fixture utilities
- `docs/`: engineering and QA documentation

Shared contract files include `app/schemas.py`, `app/api.py`, `frontend/src/types.ts`,
`frontend/src/api.ts`, database models, dependency lockfiles, Docker files, and CI workflows.
Changes to these files must be called out in the issue and PR because they can affect other tasks.

## Change discipline

- Keep the patch limited to the issue's acceptance criteria.
- Do not perform repository-wide formatting, dependency upgrades, schema migrations, or broad
  refactors unless the issue explicitly requests them.
- Never commit credentials, `.env`, OAuth tokens, generated databases, uploads, exports, test
  reports, or real customer documents.
- Preserve deterministic extraction and synthetic fixtures unless the issue explicitly changes
  that design.
- Add or update tests for behavior changes.
- Do not merge, force-push, rewrite another agent's branch, or resolve another agent's conflicts.

## Verification

Run the smallest relevant checks while iterating, then all checks for the layers changed.

Backend:

```powershell
python -m ruff check app tests scripts/gmail_auth.py scripts/process_gmail.py scripts/generate_synthetic_pdfs.py
python -m pytest --cov=app --cov-report=term-missing
```

Frontend:

```powershell
Set-Location frontend
npm test
npm run lint
npm run build
```

End-to-end changes:

```powershell
npm ci
npx playwright install chromium
docker compose up --build --wait --wait-timeout 180
npm run test:e2e
docker compose down --volumes --remove-orphans
```

If a check cannot run, report the exact command and reason. Do not claim it passed.

## Handoff

Finish with a clean, reviewable commit and a PR. The PR must state:

- issue and acceptance criteria addressed;
- files and contracts changed;
- tests run and their results;
- security, migration, dependency, or follow-up concerns;
- any checks that were not run.

The integration owner decides merge order. Before merge, update the branch from current `main`,
resolve conflicts on this task branch, and rerun affected checks.

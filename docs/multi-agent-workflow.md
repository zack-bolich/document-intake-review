# Multi-agent development workflow

This repository uses GitHub issues for coordination and pull requests for integration. Codex,
Codex Cloud, Claude Code, and Devin may work concurrently, but never in the same checkout or on
the same branch.

## Roles

- **Integration owner:** creates/scopes issues, assigns file ownership, chooses merge order, and
  merges PRs. Start with the repository owner in this role.
- **Task agent:** works one issue on one branch in one isolated environment and opens a PR.
- **Reviewer:** checks acceptance criteria, contracts, tests, and unintended changes. The reviewer
  should not silently expand or rewrite the task.

These are roles, not permanent tool assignments. Pick the agent that fits each bounded task.

## Pilot setup

1. Protect `main` on GitHub. Require pull requests and the `backend`, `frontend`, and `e2e` checks.
2. Create one GitHub issue per independently mergeable change using the task template below.
3. Label issues by area (`backend`, `frontend`, `e2e`, `docs`, or `integration`) and agent when useful.
4. Assign non-overlapping files to tasks. Treat API schemas, frontend types, models, lockfiles,
   Docker configuration, and workflows as shared contracts.
5. Create a worktree for each local agent. Codex Cloud and Devin should use their own remote
   workspace and the same branch convention.
6. Merge one PR at a time. After every merge, remaining agents update their branches from `main`
   and rerun affected tests.

## Task issue template

Copy this into a GitHub issue:

```markdown
## Outcome
One observable result this task must deliver.

## Acceptance criteria
- [ ] Verifiable behavior or artifact
- [ ] Relevant automated tests added or updated
- [ ] Required checks pass

## Ownership
- Allowed files/directories:
- Shared contract files (if any):
- Do not change:

## Dependencies
- Starting commit or prerequisite PR:
- Blocks / blocked by:

## Verification
- Commands the agent must run:
```

Avoid assigning goals such as "improve the application." Prefer an independently testable slice
such as "add an API filter and backend tests without changing the frontend contract."

## Local agent worktrees

From the repository root, create an isolated sibling worktree:

```powershell
.\scripts\New-AgentWorktree.ps1 -Agent codex -Issue 42 -Slug status-filter
```

This creates branch `agent/codex/42-status-filter` and a sibling directory such as
`document-intake-review-codex-42-status-filter`. Open that directory as the agent's workspace.

Useful commands:

```powershell
git worktree list
git branch --list "agent/*"
```

After its PR is merged, remove an unused, clean worktree from the original checkout:

```powershell
git worktree remove <exact-worktree-path>
git branch -d agent/codex/42-status-filter
```

Never remove a worktree with uncommitted work. Never share a worktree between tools.

## Cloud agents

Give Codex Cloud or Devin exactly one issue and tell it to:

1. branch from the current `main` using `agent/<agent>/<issue>-<slug>`;
2. follow `AGENTS.md`;
3. stay within the issue's ownership list;
4. push commits and open a PR, but not merge it;
5. include verification evidence in the PR.

Cloud tasks should be self-contained. If one task depends on another task's unmerged contract,
either wait or explicitly base a stacked branch on the prerequisite branch and document that in
both PRs.

## Ledgerline ownership examples

Safe parallel split:

| Task | Primary ownership | Agent example |
| --- | --- | --- |
| Parser rule and unit tests | `app/parser.py`, `tests/test_parser.py` | Codex |
| Dashboard-only presentation | `frontend/src/App.tsx`, `frontend/src/styles.css`, component tests | Claude Code |
| Independent Playwright scenario | `tests/e2e/` | Devin |
| Documentation audit | `README.md`, `docs/` | Codex Cloud |

Unsafe split: two agents independently changing `app/schemas.py`, `app/api.py`,
`frontend/src/types.ts`, and `frontend/src/api.ts`. First land the API contract in one PR, then
branch dependent backend and frontend tasks from that commit.

## Integration order

Use this order when several PRs depend on one another:

1. shared schema or interface contract;
2. backend implementation and tests;
3. frontend consumer and component tests;
4. end-to-end tests and documentation.

Green CI is necessary but not sufficient. The integration owner also checks that independently
valid changes do not contradict each other semantically.

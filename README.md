# Medium Authority Engine

Concurrent Medium content pipeline focused on finance and AI writing with strict human approval.

## What it does
- Generates weekly article drafts with citations from an allowlisted source set.
- Applies state-driven QA and style gates.
- Limits review queue concurrency (`READY_FOR_REVIEW`) to 3 items.
- Requires explicit human approval before publishing.
- Publishes via Playwright automation.
- Runs on GitHub Actions with DST-safe schedule logic for Saturday 9:00 PM ET.

## Repository layout
- `agent/` runtime package
- `config/` persona, style, roadmap, source allowlist
- `templates/` HTML templates
- `reviews/` rendered review artifacts
- `approvals/` approval gate files
- `artifacts/` sqlite db + metadata + draft files + screenshots
- `logs/` runtime logs
- `.github/workflows/` CI and scheduler workflows
- `tests/` automated tests

## Quickstart
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python -m playwright install chromium
pip install -e .
agent init-db
agent run-weekly
```

## Core commands
- `agent init-db`
- `agent run-weekly [--respect-schedule] [--count 1]`
- `agent approve --id <id>`
- `agent publish --id <id> [--dry-run]`
- `agent publish-approved`
- `agent extract-style --url <medium-url>`
- `agent list-items`

## Human approval model
Publishing is blocked unless both conditions are true:
1. state is `APPROVED`
2. `approvals/<id>.approved` exists

Approve from CLI:
```bash
agent approve --id <id>
```

## Required environment variables for publishing
- `MEDIUM_SESSION_COOKIE` (recommended), or
- `MEDIUM_EMAIL` and `MEDIUM_PASSWORD`

Optional:
- `EMAIL_CAPTURE_URL`
- `MERCURY_PARSER_API_KEY`

## GitHub + Netlify deployment (mobile access)
This repo includes a lightweight web control panel (`dashboard/`) plus Netlify Functions that trigger GitHub Actions.

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial Medium Authority Engine"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

### 2. Configure GitHub Secrets
Set these in the GitHub repo:
- `EMAIL_CAPTURE_URL` (optional)
- `MEDIUM_SESSION_COOKIE` (preferred) or `MEDIUM_EMAIL` + `MEDIUM_PASSWORD`
- `MERCURY_PARSER_API_KEY` (optional)

### 3. Deploy to Netlify
1. Create new Netlify site from this GitHub repo.
2. Build command: leave empty (static site only).
3. Publish directory: `dashboard`
4. Functions directory: `netlify/functions`

Set Netlify environment variables:
- `GITHUB_TOKEN` (fine-grained PAT with Actions read/write on this repo)
- `GITHUB_OWNER`
- `GITHUB_REPO`
- `GITHUB_BRANCH` (usually `main`)
- `GITHUB_OPS_WORKFLOW_FILE` (`ops-manual.yml`)
- `NETLIFY_DASHBOARD_KEY` (optional but recommended)

### 4. Use the mobile panel
- Open the Netlify URL.
- Trigger operations from the panel (run weekly, approve, publish, list).
- Review run status links in the same panel.
- Human approval is still enforced by `approvals/<id>.approved` and `APPROVED` state.

## Notes
- Citations are never fabricated: URLs must be present and allowlisted.
- If QA flags are found, item is blocked from moving to `READY_FOR_REVIEW`.
- Output metadata is written to `artifacts/<id>/metadata.json`.

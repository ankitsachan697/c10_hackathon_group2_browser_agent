# Outskill Browser Automation Studio

An AI-assisted browser testing workspace for creating reusable Playwright journeys, running saved scripts on demand or on a daily schedule, preserving evidence, and attempting one controlled repair when an eligible failure occurs.

## Execution model

On-demand, scheduled, saved-case, and rerun actions execute the saved Playwright script directly. n8n is used only when a user explicitly generates a journey or when an eligible failed run requests diagnosis and repair. A repaired script is executed once; a second failure is marked `NEEDS_ATTENTION`.

The workspace provides Outskill-branded Overview, Projects, Runs, Schedules, and Settings views; SQLite-backed resource history; timezone-aware daily scheduling; current and historical-snapshot reruns; recoverable evidence deletion; and screenshot, video, log, script, repair, and visual inspection.

## Quick start

```bash
cp .env.example .env
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/playwright install chromium
npm --prefix frontend install
```

Start the services in separate terminals:

```bash
PYTHONPATH=. backend/.venv/bin/uvicorn backend.server:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Open `http://localhost:3000`. All environment-specific values live in environment variables; no n8n URL, token, agent ID, model, credential, test URL, or login is committed. See [.env.example](.env.example).

## Verification

```bash
PYTHONPATH=. backend/.venv/bin/pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```

See [Architecture](ARCHITECTURE.md), [API reference](API_REFERENCE.md), [n8n contracts](N8N_AGENTS.md), and [User guide](USER_GUIDE.md).

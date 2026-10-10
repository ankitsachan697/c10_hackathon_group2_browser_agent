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
docker build -f backend/Dockerfile.runner -t outskill-browser-runner:local .
npm --prefix frontend ci
```

The backend creates a private, persistent key next to its SQLite database automatically; no manual `CREDENTIAL_ENCRYPTION_KEY` is needed for local use. Back up the database and its `.credentials.key` file together. An existing `CREDENTIAL_ENCRYPTION_KEY` remains supported for deployments and is copied to that local key file on startup when it is absent. Add `N8N_BEARER_TOKEN` only when the application should invoke the published n8n agents. Safe defaults—including endpoint, agent IDs, flags, timeouts, and the internal backend address—are tracked in `config/application.json`.

Start the services in separate terminals:

```bash
set -a; source .env; set +a
PYTHONPATH=. backend/.venv/bin/uvicorn backend.server:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Open `http://localhost:3000`. The frontend calls same-origin `/api/*` routes and Next.js proxies them to the configured backend. Credentials entered in a journey are encrypted in SQLite and decrypted only for the isolated Playwright worker.

### GitHub Secrets

Configure `N8N_BEARER_TOKEN` in repository or environment secrets when agent calls are enabled. The optional live login check uses `E2E_LOGIN_USERNAME` and `E2E_LOGIN_PASSWORD`; it no longer needs a credential key secret. GitHub Secrets do not configure a separately deployed server. On a server, persist and back up the private key file with the database, or optionally inject `CREDENTIAL_ENCRYPTION_KEY` through the host's secret manager.

### Browser execution after deployment

The runner launches Chromium locally by default. For a backend deployed on a server, set `PLAYWRIGHT_CDP_ENDPOINT` to a secured `ws://` or `wss://` Chrome DevTools endpoint. Saved scripts continue to call `chromium.launch()`; the runner redirects that call to `connect_over_cdp()` without changing the saved script. This works with a browser service or a local Chrome exposed through an authenticated private tunnel. Never expose a raw debugging port to the public internet.

## Verification

```bash
PYTHONPATH=. backend/.venv/bin/pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```

See [Architecture](ARCHITECTURE.md), [API reference](API_REFERENCE.md), [n8n contracts](N8N_AGENTS.md), and [User guide](USER_GUIDE.md).

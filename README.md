# Outskill Browser Automation Studio

An AI-assisted browser testing workspace for creating reusable Playwright journeys, running saved scripts on demand or on a daily schedule, preserving evidence, and attempting one controlled repair when an eligible failure occurs.

## Execution model

Creating a journey calls the configured n8n discovery agent, saves its validated Playwright script, and automatically runs that script once. On-demand, scheduled, project, saved-case, and rerun actions execute saved scripts directly without rediscovery. An eligible failure calls the repair agent once and gets one verification retry; a second failure is marked `NEEDS_ATTENTION`. Screenshot comparison is local, with optional bounded n8n visual review.

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

The backend creates a private, persistent key next to its SQLite database automatically; no manual `CREDENTIAL_ENCRYPTION_KEY` is needed for local use. Back up the database and its `.credentials.key` file together. An existing `CREDENTIAL_ENCRYPTION_KEY` remains supported for deployments and is copied to that local key file on startup when it is absent. Set `N8N_BEARER_TOKEN` in the backend runtime secret store to invoke published n8n agents. Without it, normal generation fails visibly; the form offers an explicitly labelled local offline mode. Safe defaults—including endpoint, agent IDs, flags, timeouts, and the internal backend address—are tracked in `config/application.json`.

Start the services in separate terminals:

```bash
set -a; source .env; set +a
PYTHONPATH=. backend/.venv/bin/uvicorn backend.server:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Open `http://localhost:3000`. The frontend calls same-origin `/api/*` routes and Next.js proxies them to the configured backend. Credentials entered in a journey are encrypted in SQLite and decrypted only for the isolated Playwright worker.

The create screen shows a durable operation feed. Once a run exists, its Activity tab shows observed, redacted Playwright actions, attempt outcomes, repair, and visual-review events. n8n internals appear only if the agent publishes them; the UI does not fabricate internal actions. Screenshots, video, saved scripts, and visual differences remain available as run evidence.

### GitHub Secrets

Configure `N8N_BEARER_TOKEN` in repository or environment secrets when agent calls are enabled. The optional live login check uses `E2E_LOGIN_USERNAME` and `E2E_LOGIN_PASSWORD`; it no longer needs a credential key secret. GitHub Secrets do not configure a separately deployed server. On a server, persist and back up the private key file with the database, or optionally inject `CREDENTIAL_ENCRYPTION_KEY` through the host's secret manager.

### Browser execution after deployment

For a Docker worker on your own Mac, follow the [local headed Chromium setup](docs/LOCAL_HEADED.md).

Headless runs use the isolated Docker worker. To watch a run on your computer when the backend is remote, pair the local browser companion:

1. Set `RUNNER_BROWSER_LOCATION=hosted`, `RUNNER_RELAY_BASE_URL` to a WebSocket-reachable backend URL (`wss://...` in deployment), and a private `COMPANION_ADMIN_TOKEN` in the backend runtime. The relay URL must be reachable from inside the runner container. The reverse proxy must route `/api/companions/relay/*` WebSockets directly to FastAPI; the Next.js HTTP proxy is not the WebSocket endpoint.
2. An operator calls `POST /api/companions/pair-codes` with `X-Companion-Admin-Token`. The returned code expires after five minutes and can be used once.
3. On the computer where the browser should appear, run `backend/.venv/bin/python -m companion.browser_companion pair --server https://YOUR_BACKEND --code YOUR_CODE --device-name My-laptop`, then `backend/.venv/bin/python -m companion.browser_companion run --server https://YOUR_BACKEND`. The device credential stays in a private local file. The companion requires HTTPS except for loopback development.
4. Choose **Watch in browser** and the online device. The companion asks for local approval for that run before opening Chromium. If it is offline or approval times out, the run becomes **Needs attention**; no headless fallback occurs.

The relay transfers scoped CDP frames, not generated Python. Chromium listens only on the companion's loopback interface; no public Chrome debugging port is needed. For an advanced private browser service, `PLAYWRIGHT_CDP_ENDPOINT` remains available, but it is not a way to reach an arbitrary laptop automatically. Run the backend relay in one Uvicorn process; in-memory active sessions are not shared across workers. Keep the operator token and device credential out of browser-facing configuration and logs.

## Verification

```bash
PYTHONPATH=. backend/.venv/bin/pytest -q
PYTHONPATH=. backend/.venv/bin/pytest companion/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```

See [Architecture](ARCHITECTURE.md), [API reference](API_REFERENCE.md), [n8n contracts](N8N_AGENTS.md), and [User guide](USER_GUIDE.md).

# Watch local Chromium while keeping the worker isolated

The default Docker worker cannot display Chromium on macOS. Use the local
companion: generated Python stays in Docker, while a scoped browser connection
drives visible Chromium on your computer. Do not enable unsandboxed execution
or expose Chrome's debugging port.

## 1. Configure the backend

Run all commands from the repository root. Keep the existing n8n token in your
private runtime environment. Add a strong, stable `COMPANION_ADMIN_TOKEN` to
your **gitignored** local `.env` (or inject it through your secret manager).
This is a separate secret used to authorize pairing, not the n8n token.
Changing it invalidates existing device credentials, requiring new pairing.
Generate it once with `backend/.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`
and save the result as `COMPANION_ADMIN_TOKEN=...` in the private `.env`.

Stop the existing backend with Ctrl+C in its terminal. Start it with these
non-secret overrides; they leave the Docker runner enabled:

```bash
set -a
source .env
set +a
export RUNNER_BROWSER_LOCATION=hosted
export RUNNER_RELAY_BASE_URL=ws://host.docker.internal:8000
PYTHONPATH="$PWD" backend/.venv/bin/python -m uvicorn backend.server:app \
  --host 127.0.0.1 --port 8000
```

`hosted` selects companion routing, even when the backend itself is on your
laptop. `host.docker.internal` lets the Docker worker reach the backend relay.
Use one backend process; active relay sessions are not shared between workers.

## 2. Pair and start the companion

In a second terminal at the repository root, load the same private `.env`.
This request issues a one-use pairing code without printing the operator token.
The Python snippet also exchanges it immediately and saves a device credential
in a private file. No secret needs to be copied between terminals.

```bash
set -a
source .env
set +a
backend/.venv/bin/python - <<'PY'
import asyncio
import os
import httpx
from companion.browser_companion import pair, DEFAULT_DEVICE_FILE

async def setup():
    server = 'http://127.0.0.1:8000'
    token = os.environ.get('COMPANION_ADMIN_TOKEN')
    if not token:
        raise SystemExit('Set COMPANION_ADMIN_TOKEN in your private backend environment first.')
    async with httpx.AsyncClient(base_url=server, timeout=10) as client:
        response = await client.post('/api/companions/pair-codes',
            headers={'X-Companion-Admin-Token': token})
        response.raise_for_status()
        code = response.json()['data']['code']
    await pair(server, code, 'My local Chromium', DEFAULT_DEVICE_FILE)
    print('Local Chromium paired. Device credential saved privately.')

asyncio.run(setup())
PY
backend/.venv/bin/python -m companion.browser_companion run \
  --server http://127.0.0.1:8000
```

Pair once; on later starts run only the final companion command. Keep its
terminal open. If Chromium is not installed, install the matching browser with
`backend/.venv/bin/python -m playwright install chromium`.

## 3. Start a visible journey

On **New journey**, click **Refresh browser status**, select **Watch in browser**,
and select **My local Chromium**. Enter the objective, target URL, and optional
credentials, then click **Verify & record live**. In the companion terminal,
answer `y` to the approval prompt. Chromium opens locally; the dashboard shows
observed actions and saved evidence. It closes when the browser session ends.

The Runs page's existing rerun buttons currently default to headless mode.
For a headed saved-script rerun, the API accepts
`{"mode":"snapshot","browser_mode":"headed","companion_id":"YOUR_DEVICE_ID"}`
at `POST /api/runs/YOUR_RUN_ID/rerun`. Get the non-secret device ID from
`GET /api/companions`. This does not invoke discovery again.

These loopback URLs are for local development only. A deployed backend requires
HTTPS for companion requests and WSS for its relay, plus the existing pairing
and per-run approval controls.

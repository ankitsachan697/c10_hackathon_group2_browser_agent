# Browser Automation Studio user guide

## Create a journey

1. Open **New journey**.
2. If this is the first run, select **Create first project**, give the project a name, and create it. The project is selected automatically. For later journeys, choose **+ New project…** in the selector.
3. Enter a journey name, target URL, and objective. Describe actions and expected results; do not put credentials in the objective.
4. On **Browser and credentials**, optionally enter a username and password. The password is masked. Both values are encrypted before SQLite persistence and are never embedded in the generated script or sent to n8n.
5. Review the masked summary, then select **Generate and save**. Generation is the only point where the Flow Discovery agent can be called.

Generated scripts read `AUTH_USERNAME` and `AUTH_PASSWORD`. At execution time the backend decrypts the stored values in memory and passes them only to the isolated Playwright worker.

## Run and inspect

Saved-script execution is deterministic. **Run now**, a daily schedule, a project run, and current or historical reruns all execute the saved Playwright script directly. They do not regenerate it.

Run detail retains:

- immutable Playwright script snapshot and version;
- every attempt and redacted stdout/stderr;
- milestone and failure screenshots;
- flushed `.webm` session video when available;
- DOM/log artifacts;
- diagnosis, repair, and the single verification retry.

An eligible selector or timeout failure gets at most one repair retry. A second failure becomes **Needs attention**.

## Daily schedules

Create a daily local time and IANA timezone from **Schedules**. Use **Run now** to execute the scheduled scope immediately. The scheduler restores enabled jobs after backend restart and prevents overlapping runs for the same journey.

## Configuration and secrets

Safe defaults are tracked in `config/application.json`. Deployment environment variables can override them. Only these values are secrets:

- `N8N_BEARER_TOKEN` authenticates optional n8n generation and repair calls.
- `CREDENTIAL_ENCRYPTION_KEY` encrypts reusable journey credentials.

Generate a credential key with:

```bash
backend/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Keep it stable for the lifetime of stored credentials. If it is lost or changed, existing credentials cannot be decrypted and must be replaced. Never commit either secret or expose them through a `NEXT_PUBLIC_*` variable.

For a remote backend, set `PLAYWRIGHT_CDP_ENDPOINT` to an authenticated private `ws://` or `wss://` Chrome DevTools endpoint. Never publish a raw browser debugging port.

## Connection failures

The frontend proxies `/api/*` through Next.js. If the backend is stopped, the journey screen shows **Backend is unavailable** with a retry action instead of a runtime overlay. Service badges independently report API, runner, scheduler, and n8n readiness.

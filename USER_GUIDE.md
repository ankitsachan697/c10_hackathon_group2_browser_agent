# Browser Automation Studio user guide

## Create a journey

1. Open **New journey**.
2. If this is the first run, select **Create first project**, give the project a name, and create it. The project is selected automatically. For later journeys, choose **+ New project…** in the selector.
3. Enter a journey name, target URL, and objective. Describe actions and expected results; do not put credentials in the objective.
4. On the same page, optionally enter a username and password and choose **Headless** or **Watch in browser**. The password is masked. Both values are encrypted before SQLite persistence and are never embedded in the generated script or sent to n8n.
5. Select **Generate and run**. The discovery agent generates a saved script, and the first run starts automatically. Choose the clearly labelled offline option only when you intend to use local script synthesis instead of n8n. The activity panels show generation and browser events as they are persisted.

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
The **Activity** tab shows observable browser actions, while **Visual** shows the baseline or comparison outcome. The first passing screenshot establishes the baseline; later screenshots are compared without silently replacing it. Visual-agent errors do not turn a functionally passing test into a failed one.

## Daily schedules

Create a daily local time and IANA timezone from **Schedules**. Use **Run now** to execute the scheduled scope immediately. The scheduler restores enabled jobs after backend restart and prevents overlapping runs for the same journey.

## Configuration and secrets

Safe defaults are tracked in `config/application.json`. Deployment environment variables can override them. Only these values are secrets:

- `N8N_BEARER_TOKEN` authenticates n8n discovery, repair, and visual review calls. Agent IDs and feature flags in tracked configuration are not credentials. GitHub Secrets affect CI; a deployed backend needs the token in its own runtime secret store.
- The backend automatically creates a private `.credentials.key` file beside the SQLite database to encrypt reusable journey credentials. `CREDENTIAL_ENCRYPTION_KEY` is an optional deployment override, not a local setup requirement.

Back up the database and key file together. If the key is lost or changed, existing credentials cannot be decrypted and must be replaced. Never commit the key or expose it through a `NEXT_PUBLIC_*` variable. Logs, text evidence, and repair packets redact known credentials and recognizable payment details; screenshots and videos blur common credential and payment input fields. Review evidence before sharing because arbitrary page content may still contain sensitive data.

For a remote backend, set `PLAYWRIGHT_CDP_ENDPOINT` to an authenticated private `ws://` or `wss://` Chrome DevTools endpoint. A headed run otherwise opens Chromium on the server, not the presenter's laptop. Never publish a raw browser debugging port.

## Connection failures

The frontend proxies `/api/*` through Next.js. If the backend is stopped, the journey screen shows **Backend is unavailable** with a retry action instead of a runtime overlay. Service badges independently report API, runner, scheduler, and n8n readiness.

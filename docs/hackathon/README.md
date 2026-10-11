# Group2 Browser Automation Studio showcase

Use **Demo lab** in Studio to create an isolated, deployable shop. It supports registration, login, cart, shipping, and a synthetic checkout. No real payment details or purchases are involved. Registration accounts exist only in the current tab; reload resets them.

## Share with the hackathon team

- [79-second real walkthrough](group2-showcase.mp4), with [duration/checksum receipt](group2-showcase.receipt.json). Captions disclose shortened waits; no simulated agents or mocked results appear in this capture.
- [Detailed interactive architecture](architecture.html), with source links and four guided views.
- [Run and agent evidence](run-evidence.json) and [published agent versions](agent-versions.json).

Verified on 2026-10-11: first discovery/run PASSED in one attempt; deliberately stale checkout PASSED_AFTER_REPAIR in two attempts (one retry), with the verified fix saved as version 2; visual redesign PASSED functionally while Pixelmatch found 3.347% changed pixels; rejected checkout NEEDS_ATTENTION in one attempt with zero repair calls. All three configured n8n agents were invoked: discovery, repair, and numeric visual review. Discovery and visual invocations are evidenced in activity/review records; repair also has a durable invocation record.

Fresh checks after independent review fixes: 171 backend tests passed, including a native Chromium failure-evidence regression. The showcase checks also passed 42 frontend tests, six native Chromium browser tests, lint, and production build. Raw capture (93 seconds) and browser evidence remain locally under `artifacts/showcase/session-20261011-final-handoff/`, excluded from Git. The packaged 79.12-second video is included in this repository for colleagues.

## Start locally

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -m playwright install chromium
docker build -f backend/Dockerfile.runner -t outskill-browser-runner:local .
```

Inject `N8N_BEARER_TOKEN` from your private runtime secret store. Non-secret defaults are in `config/application.json`. If you use a gitignored local `.env`, load it without printing its contents:

```bash
PYTHONPATH="$PWD" backend/.venv/bin/python -c 'import os; from starlette.config import Config; os.environ.update(Config(".env").file_values); import uvicorn; uvicorn.run("backend.server:app", host="127.0.0.1", port=8000)'
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000/demo-lab`. Keep the isolated Docker runner enabled. Do not enable unsandboxed host execution for generated scripts. Credentials are encrypted with the backend's automatically created private key; retain the database and key together.

The command parses `.env` as data, including values containing spaces; it does not execute it as a shell script. Leave autoreload off when recording: editing Python files can interrupt browser jobs. On backend startup, abandoned active runs become NEEDS_ATTENTION with an interruption audit entry; they are not silently replayed. Review their evidence before rerunning.

## Reproduce the demonstration

1. Click **New scenario**, then **Create demo journey**. Create/select a project. The objective, target, and synthetic username are supplied; enter the public demo password shown in Demo lab. Disable local offline generation so the real discovery agent is required.
2. Click **Verify & record live**. The discovery agent returns a plan and Python Playwright script; the isolated worker performs and records the actual browser actions. Check the intermediate login assertion and final order confirmation, script, screenshots, and recording.
3. Enable **Change checkout locator** in the same scenario. From its run, click **Run current script**. Checkout's accessible name and ID have changed. The saved script fails, the repair agent receives the bounded error and masked live DOM, and exactly one repaired retry runs. A successful retry becomes the next saved script version. The original run snapshot stays unchanged.
4. Leave the changed locator enabled and enable **Apply visual redesign**. Replay **current** script, not the older snapshot. Functional checkout should pass while **Visual** shows DIFFERENCE, with baseline/current/heatmap evidence. The baseline stays locked. Comparison currently uses the first captured screenshot, not all milestone screenshots.
5. Enable **Reject checkout**. Replay current script. A real product assertion must fail with NEEDS_ATTENTION and no repair invocation. Do not label this product failure as healed.
6. Inspect Overview counts and Runs. Completed runs can be deleted after confirmation; active runs cannot. Evidence moves into recoverable artifact trash. The saved journey and canonical visual baseline remain.

The seed account is public synthetic data: `demo@example.test` / `DemoPass123!`. For registration use another synthetic email and a password of at least eight characters. The native browser smoke suite exercises new-account registration, wrong password, duplicates, cart, checkout, and business rejection.

## Agent boundaries and reliability

Discovery generates code from the objective and a bounded observed control summary; it does **not** independently execute actions in n8n. Actual observed actions come from instrumented Playwright and appear live in Studio. n8n discovery, repair, and numeric visual review are audited separately. The visual agent receives a bounded numeric comparison summary, not the raw images; local Pixelmatch determines the visual verdict.

Saved, scheduled, on-demand, and rerun executions do not rediscover the journey. Locator/timing failures may invoke repair once. Authentication, infrastructure, and assertion failures require attention. Repairs that remove or alter original Python assertions, positive/negative Playwright expectation calls, or locator outcome waits are rejected, as are checks moved to a different AST position or control-flow context. This guard is intentionally conservative; harmless broader rewrites may need manual review, and it is not a proof of arbitrary generated-code semantics. Version-and-script compare-and-swap prevents an old repair from overwriting a newer saved script. Failure evidence sanitizes a detached DOM clone and masks screenshot pixels without clearing the live form, so a caught locator error can safely fall back to another locator.

Discovery and repair prompts are versioned in `n8n_workflows/agent_prompts/`. Their published instructions were corrected for supported APIs, exact accessible names, complete target URLs, evidence milestones, and assertion preservation. Model, credentials, and tools were not changed. Keep n8n credentials private; neither the video nor repository contains the bearer token.

## Deployment and visible local Chromium

The shop is served by FastAPI under `/api/demo-shop/<scenario>`; Next.js's same-origin API proxy makes it accessible at the deployed Studio origin. Create a **fresh scenario at the deployed origin**: saved localhost URLs from a developer's machine are not transferable to a server.

Persist SQLite, its private credential key, and the artifacts directory. Keep the configured n8n secret in the server's secret manager (GitHub Actions secrets must be explicitly injected during deployment; they do not automatically become runtime environment variables). Ensure the server worker can reach the deployed target. For same-host Docker targets on Linux, bind the relevant service to `0.0.0.0`; a service bound only to loopback is not reachable through the Docker host gateway. Apply your deployment's authentication, TLS, and access restrictions to Studio/API; this change does not add a public multi-tenant authorization layer.

For visible Chromium on a laptop, follow [local headed setup](../LOCAL_HEADED.md). Keep Python execution in Docker; the paired companion exposes only a scoped, approved browser connection. Remote deployment needs HTTPS companion requests, a WSS relay reachable from the worker, and reverse-proxy WebSocket routing directly to FastAPI. Use one backend process: active relay sessions, overlap guards, and background task handles are process-local. No unauthenticated public Chrome debugging port is needed. Remote infrastructure deployment itself is not part of the locally verified capture.

## Capture and checks

```bash
backend/.venv/bin/python scripts/record_showcase.py --output artifacts/showcase/my-session
backend/.venv/bin/python scripts/package_showcase.py artifacts/showcase/my-session/evidence.json docs/hackathon/group2-showcase.mp4
backend/.venv/bin/python -m pytest -q
cd frontend
npm test -- --run
npm run lint
npm run build
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 npx playwright test tests/browser/demo-shop.spec.ts tests/browser/demo-lab.spec.ts tests/browser/projects-workspace.spec.ts --workers=1
```

Capture drives the actual Studio UI in headed Chromium, requires genuine configured n8n agents, and fails if expected outcomes are not observed. Packaging rejects incomplete captures, retains chronological chapters, explicitly labels shortened waits, and verifies a duration below 120 seconds. The separate business-rejection run is expected to fail functionally; successful verification means this failure is correctly reported.

The standalone [architecture diagram](architecture.html) includes source-linked components and guided views for first run, single-retry repair, local Chromium, and locked visual review. Its deterministic validation and real-browser containment evidence are separate from perceptual review; see the receipt below.

```text
diagram_type: architecture
output: docs/hackathon/architecture.html
specification_sha256: 4908ab74b0c0f9f1fc0fd4552bef55af754e40369532c92a4629cceea4a3aaf1
artifact_sha256: a890bf57dd359efb30cfa67e1393b861550ec5012b00b1a7ab2168f087065d65
validation: 9/9 showcase, 0 errors, 0 warnings
browser_evidence: passed (1440x900, 1600x1000, 1920x1080, 2048x1320)
visual_review: passed (1440x900 light and 2048x1320 dark inspected)
correction_rounds: 1
```

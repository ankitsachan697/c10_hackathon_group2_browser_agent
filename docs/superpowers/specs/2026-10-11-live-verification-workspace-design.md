# Live Verification Workspace — Design

## Purpose

Make the New Journey page a single, persistent place to describe a browser objective, configure a first run, watch confirmed Playwright actions, and inspect its saved evidence. The experience borrows the information layout of `xray_lens` while retaining this project's Outskill theme, Next.js frontend, FastAPI backend, n8n discovery/repair agents, and Python Playwright runner. It must work for arbitrary target URLs and objectives; no site-specific selectors or credentials belong in the UI.

## User flow

1. On `/journeys/new`, the user enters an objective, project, journey name, start URL, optional username/password, and browser mode. The main action reads **Verify & record live**. When no project exists, creation remains available without losing typed fields.
2. On submit, the page starts the existing generation operation. n8n discovery produces and saves a Playwright script; the runner executes its first run. Saved-case, scheduled, on-demand, and rerun execution continue to use the saved script directly, without rediscovery.
3. The page keeps the configuration visible but distinguishes it from the live session. Discovery status and planned steps come from operation events. Confirmed browser action progression and console messages come from run events; the UI must never mark an objective step passed merely because an action count advanced.
4. The live section follows queued, discovery, execution, optional repair and one retry, visual review, and final status. If a run needs manual attention, show that state and the diagnosis without claiming success.
5. Once a run exists, tabs expose **Steps & Logs**, **Playwright Script**, **Screenshots**, **Recording**, and **Visual**. Tabs update as artifacts arrive. The Runs sidebar remains the durable history and rerun destination.

## Page layout and component boundaries

- `JourneyForm` becomes the configuration/composer section and retains current project loading, first-project dialog, password preservation, browser companion choice, idempotent submit, and operation restoration.
- A focused live-session component owns polling/rendering of operation and run events and the step-versus-console switcher. It shows actual recorded action statuses, source, time, and a scrollable console. It may use the existing `RunActivity` event API but must not duplicate poll loops needlessly.
- A reusable result-tabs component displays the saved script and artifacts from `GET /api/runs/{id}`. Screenshot and recording tabs render safe inline previews from `/api/artifacts/{id}` with direct open/download links. Empty/loading/failed evidence states are explicit.
- The run detail page should use the same evidence presentation so results remain understandable after navigating away. Its existing rerun actions stay on the run detail page; the creation page links to it.
- Styling follows the existing black/charcoal surface, lime accent, Outskill logo, and responsive CSS. It should adapt to narrow widths, support keyboard tab navigation, visible focus, accessible tab labels, and reduced motion.

## Data and state contract

- Reuse `POST /api/operations/generations`, `GET /api/operations/{id}`, both operation/run event feeds, `GET /api/runs/{id}`, and artifact routes. No new execution path or Kane integration is introduced.
- Generation operation `COMPLETED` means generation orchestration finished; the displayed pass/fail outcome comes from the run status (`PASSED`, `PASSED_AFTER_REPAIR`, or `NEEDS_ATTENTION`).
- Planned discovery steps are taken from the `generation.completed` event's `discovered_steps`. Executed steps are run action events (`action.started`, `action.finished`, `action.failed`) with their own statuses. They are visually separate until a reliable action-to-objective mapping exists.
- Event polling uses sequence cursors, deduplicates events, and resumes after refresh from the existing stored operation ID. Run/artifact polling stops or backs off after a terminal state.
- Passwords remain masked, are never displayed in event or console content, and are cleared from the form only after accepted submission. The worker receives them through the existing encrypted credential handoff. No screenshot is requested while credential fields are filled.
- Artifacts are rendered only for their declared media kind/type; missing, deleted, or unsupported artifacts have a non-breaking fallback.

## Error handling and verification

- Project/API connection errors remain retryable. The submit action cannot double-create a journey while an operation is active. Refresh restores the live session or reports an unavailable operation without an unhandled rejection.
- Failed discovery, failed browser actions, repair failure, and visual unavailability are distinct states. A failed run keeps its logs, script, and any evidence accessible.
- Frontend tests cover configuration, credential blur/autofill preservation, submit/restoration, real action progression versus planned discovery, final run status, empty/available artifacts, and rerun navigation. Existing backend tests remain green because execution contracts are unchanged.
- Verify with frontend tests, lint, production build, backend tests, and a browser walkthrough using a real saved run. Do not use Kane CLI.

## Out of scope

Changing n8n agent workflows, introducing a new browser-control service, exposing secrets in UI, and replacing Next.js with Vite are not part of this design.

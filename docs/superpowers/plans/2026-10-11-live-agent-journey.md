# Live Agent Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Creating a journey invokes the real discovery agent, executes the saved script once, streams genuine redacted events, performs one eligible repair retry, and records visual comparison with optional n8n review.

**Architecture:** SQLite-backed generation operations and run events provide reconnectable state. A generation coordinator calls n8n, saves a validated script, then dispatches the existing run orchestrator. The orchestrator owns functional status, one repair retry, and post-run visual review; the frontend subscribes to persisted events and presents a single-form creation flow.

**Tech Stack:** Python 3/FastAPI/SQLite/Playwright/pytest; Next.js 16/React/TypeScript/Vitest; existing n8n MCP adapter.

**Spec:** `docs/superpowers/specs/2026-10-11-live-agent-journey-design.md`

## Global Constraints

- Scheduled, on-demand, saved-case, project, and rerun triggers execute saved scripts directly; they never regenerate.
- One eligible repair and one verification retry maximum.
- No credentials or payment data in n8n prompts, events, logs, or generated scripts.
- Missing/disabled n8n must fail visibly; local synthesis requires explicit offline selection and source labelling.
- Run and operation events are durable, ordered, bounded, and reconnectable.
- Visual-agent failure cannot erase a functional result.
- The first run starts automatically after successful generation; later runs do not regenerate.
- No “enterprise” product copy; preserve Outskill visual identity.

## Review Focus

1. Duplicate create submission/reload must not produce two journeys or two first runs (Task 3 idempotency test).
2. n8n returns HTTP 200 with an error or malformed JSON: generation must fail, never silently synthesize (Task 2 contract test).
3. A fill action contains a password or card value: events must omit the value even before persistence (Task 4 redaction test).
4. A browser run passes but visual review fails: functional status remains passed with visual `ERROR` (Task 6 test).
5. Client reconnects after missing events: `after_seq` returns every later event in order without replaying older events (Task 1 test).

## File Structure and Interfaces

- `backend/event_store.py`: `EventStore.append(scope_type: str, scope_id: str, source: str, kind: str, payload: dict) -> dict` and `EventStore.list_after(scope_type: str, scope_id: str, after_seq: int, limit: int = 200) -> list[dict]`; redacts before insert.
- `backend/generation.py`: `GenerationCoordinator.submit(request: dict, idempotency_key: str) -> dict`, `GenerationCoordinator.execute(operation_id: str) -> None`, `GenerationCoordinator.recover() -> None`; delegates persistence, n8n, and first run.
- `backend/n8n_client.py`: `generate_flow_script(..., offline: bool = False)` raises typed `AgentError` unless explicitly offline; `review_visual(summary: dict) -> dict` invokes the configured visual agent.
- `backend/action_events.py`: `instrument_script(script: str) -> str` emits safe `ACTION_EVENT` JSON lines for supported Playwright calls; no argument values are serialized.
- `backend/orchestrator.py`: `run_journey(..., headed: bool = False, event_sink: Callable | None = None) -> dict` passes mode/log callback, persists lifecycle and agent events, and invokes a visual review service.
- `backend/visual_review.py`: `VisualReview.review(journey_id: str, run_id: str, screenshots: list[str]) -> dict` owns first-baseline and deterministic comparison, then optional bounded n8n summary.
- `frontend/components/journeys/JourneyForm.tsx`: one-page form; `frontend/components/runs/RunActivity.tsx`: reconnectable event display.

### Task 1: Durable Events and Public Feed

**Files:** Modify `backend/database.py`, `backend/api/runs.py`, `backend/api/__init__.py`; create `backend/event_store.py`, `backend/api/operations.py`, `backend/tests/test_event_store.py`.

**Interfaces:** Produces `EventStore.append/list_after` and `GET /api/operations/{id}`, `GET /api/operations/{id}/events?after_seq=N`, `GET /api/runs/{id}/events?after_seq=N`. The feed may use bounded polling first; sequence IDs preserve an SSE upgrade path.

- [ ] **Step 1: Write failing tests** for unique increasing sequence numbers, redaction, `after_seq` reconnect ordering, maximum 200 events, and an old database migrating without losing journeys/runs.
- [ ] **Step 2: Run** `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_event_store.py -q`; expect failures for absent schema/store.
- [ ] **Step 3: Implement** `generation_operations`, `activity_events`, and `agent_invocations` migration in `Database.initialize()` plus `EventStore` and read-only API routes. Event payload size limit: 4 KiB; feed limit: 200.
- [ ] **Step 4: Run** the focused test and `backend/tests/test_repositories.py`; expect pass.
- [ ] **Step 5: Commit** event schema/store/API as `feat: persist reconnectable activity events`.

### Task 2: Honest n8n Invocation Contracts

**Files:** Modify `backend/n8n_client.py`, `backend/config.py`, `backend/api/journeys.py`, `config/application.json`, `backend/tests/test_n8n_workflows.py`; create `backend/tests/test_n8n_contract.py`.

**Interfaces:** Produces `AgentError(code: str, message: str)`, `N8nClient.generate_flow_script(url, task_objective, credentials_meta, offline=False) -> dict`, `N8nClient.review_visual(summary: dict) -> dict`. Success includes `agent_id`, `agent_source`, and optional usage metadata only if returned by n8n.

- [ ] **Step 1: Write failing tests** for missing token/disabled flag → `AGENT_NOT_CONFIGURED`, MCP error/timeout → `AGENT_UNAVAILABLE`, malformed script response → `AGENT_RESPONSE_INVALID`, explicit offline → labelled local output, and bounded visual payload without credentials.
- [ ] **Step 2: Run** `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_n8n_contract.py -q`; expect failures from current silent fallback.
- [ ] **Step 3: Implement** typed errors and strict response parsing. Keep token in backend runtime secrets. Pass agent IDs from config; do not log or return bearer values. Correct the MCP response-envelope handling using authenticated, sanitized fixture captures or an integration probe; do not assume `ok`/`response` shape.
- [ ] **Step 4: Run** contract and existing n8n workflow tests; expect pass.
- [ ] **Step 5: Commit** as `fix: make n8n calls explicit and observable`.

### Task 3: Generation Operation and Automatic First Run

**Files:** Create `backend/generation.py`, `backend/api/operations.py`, `backend/tests/test_generation.py`; modify `backend/api/journeys.py`, `backend/api/context.py`, `backend/server.py`.

**Interfaces:** `POST /api/operations/generations` accepts existing journey-create fields, `browser_mode: "headless" | "headed"`, `offline: bool = false`, and `Idempotency-Key`; returns `202` with operation ID. `GenerationCoordinator.execute()` publishes journey ID then first run ID through events. Existing `/api/journeys/generate` stays as compatibility adapter with no automatic run.

- [ ] **Step 1: Write failing tests** for immediate `202`, successful agent call → validated script saved → exactly one first run, credentials never passed to n8n, duplicate key returns the same operation, reconnect/recovery does not duplicate work, and missing token yields visible failed operation without journey creation.
- [ ] **Step 2: Run** `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_generation.py -q`; expect failures.
- [ ] **Step 3: Implement** coordinator and transactional operation claims. Use FastAPI startup/lifespan to resume queued operations. Reject scripts failing `validate_browser_script` before persistence. Do not create a run until the script is saved.
- [ ] **Step 4: Run** generation and API tests; expect pass.
- [ ] **Step 5: Commit** as `feat: generate and run new journeys once`.

### Task 4: Real Browser Action and Lifecycle Events

**Files:** Create `backend/action_events.py`, `backend/tests/test_action_events.py`; modify `backend/runner.py`, `backend/orchestrator.py`, `backend/tests/test_runner_remote_browser.py`, `backend/tests/test_orchestrator.py`.

**Interfaces:** `instrument_script(script: str) -> str` inserts safe action start/outcome markers for supported calls. `PlaywrightRunner.execute_script(..., on_log=..., headed=False)` already exists; orchestrator adds `headed` and `event_sink` parameters. `EventStore.append` receives sanitized event types, never raw fill values.

- [ ] **Step 1: Write failing tests** for `goto/click/fill/press/check/select_option/expect/screenshot` events, no fill argument value, ordered start/finish, action failure, stdout/stderr redaction, headed propagation, and no fabricated internal n8n actions.
- [ ] **Step 2: Run** focused action/runner/orchestrator tests; expect failures.
- [ ] **Step 3: Implement** AST-aware instrumentation without changing script behavior. Parse marker lines in runner stdout into typed events; continue storing redacted ordinary output. Emit orchestration transitions and agent-call start/outcome through the same sink.
- [ ] **Step 4: Run** focused tests and script-policy tests; expect pass.
- [ ] **Step 5: Commit** as `feat: stream observed browser actions`.

### Task 5: Repair State and One Retry with Event Evidence

**Files:** Modify `backend/orchestrator.py`, `backend/failure_context.py`, `backend/tests/test_orchestrator.py`, `backend/tests/test_failure_context.py`.

**Interfaces:** Uses Task 4 `event_sink` and Task 2 `AgentError`; returns existing `RunStatus` values. Agent invocation records include ID, source, duration, category, outcome, and usage only when returned.

- [ ] **Step 1: Write failing tests** for eligible failure → one repair call/retry, ineligible failure → zero repair calls, invalid/unavailable repair → `NEEDS_ATTENTION`, original and retry attempts retained, and repair events excluding secrets.
- [ ] **Step 2: Run** focused tests; expect failures in event/invocation assertions.
- [ ] **Step 3: Implement** event and invocation persistence at the existing repair boundary, without changing the one-retry decision rule.
- [ ] **Step 4: Run** focused tests; expect pass.
- [ ] **Step 5: Commit** as `feat: expose repair lifecycle honestly`.

### Task 6: Visual Baseline, Diff, and Agent Review

**Files:** Create `backend/visual_review.py`, `backend/tests/test_visual_review.py`; modify `backend/orchestrator.py`, `backend/api/runs.py`, `frontend/lib/types.ts`.

**Interfaces:** `VisualReview.review(journey_id, run_id, screenshots) -> dict` produces `BASELINE_NEEDED | BASELINE_CREATED | MATCH | DIFFERENCE | UNAVAILABLE | ERROR`; the run detail exposes `visual_outcome` and comparison artifacts. Calls `N8nClient.review_visual` only with bounded metrics/references.

- [ ] **Step 1: Write failing tests** for successful first run auto-establishing a labelled baseline, unsuccessful first run → `BASELINE_NEEDED`, second run match/difference without overwriting baseline, absent screenshot → `UNAVAILABLE`, n8n visual invoked with bounded non-secret data, and agent failure leaving functional `PASSED` unchanged.
- [ ] **Step 2: Run** `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_visual_review.py -q`; expect failures.
- [ ] **Step 3: Implement** safe baseline storage and local `compare_images` integration. Persist review status/metrics/artifact IDs; emit visual lifecycle events. Never promote a baseline silently after a difference.
- [ ] **Step 4: Run** visual and orchestrator tests; expect pass.
- [ ] **Step 5: Commit** as `feat: compare screenshots and request visual review`.

### Task 7: Single-Form Creation and Live Run UI

**Files:** Create `frontend/components/journeys/JourneyForm.tsx`, `frontend/components/runs/RunActivity.tsx`, `frontend/tests/run-activity.test.tsx`; modify `frontend/app/journeys/new/page.tsx`, `frontend/app/runs/[id]/page.tsx`, `frontend/components/runs/RunLogs.tsx`, `frontend/app/globals.css`, `frontend/lib/types.ts`, `frontend/tests/journey-create.test.tsx`.

**Interfaces:** Form submits `POST /api/operations/generations` with idempotency key and mode. Operation polling switches to run polling when `run_id` appears. Run activity uses `GET /api/runs/{id}/events?after_seq=N`; optional SSE enhancement uses the same sequence cursor.

- [ ] **Step 1: Write failing component tests** for one aligned form, inline first project, masked credentials, headless/headed choice, one submit, generation error, automatic run transition, live event ordering/reconnect, and no empty Logs tab.
- [ ] **Step 2: Run** `npm --prefix frontend test -- --run`; expect new tests to fail.
- [ ] **Step 3: Implement** one-page form and responsive CSS. Display true agent source/ID, script version, browser target, action log, repair result, and visual status. Never render secrets from event data.
- [ ] **Step 4: Run** frontend tests, lint, and build; expect pass.
- [ ] **Step 5: Commit** as `feat: simplify journey creation and show live activity`.

### Task 8: Integration and Documentation

**Files:** Modify `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md`, `API_REFERENCE.md`, `.env.example`; add integration assertions to `backend/tests/test_api.py` and frontend tests.

**Interfaces:** No new runtime interfaces. Documents runtime n8n token requirement, safe tracked flags, offline mode, first-run behavior, and that a saved-script passing run makes no LLM call.

- [ ] **Step 1: Write/extend integration test** proving create → discovery → first run → events → repair or pass → visual, and saved rerun skips discovery.
- [ ] **Step 2: Run** focused integration test; expect failure until all prior tasks are wired.
- [ ] **Step 3: Update** docs and configuration guidance; explicitly distinguish GitHub Secrets from a local/backend runtime token.
- [ ] **Step 4: Run** `PYTHONPATH=. backend/.venv/bin/pytest -q`, `npm --prefix frontend test -- --run`, `npm --prefix frontend run lint`, `npm --prefix frontend run build`, and `git diff --check`; expect all pass.
- [ ] **Step 5: Commit** as `docs: explain live agent and first-run lifecycle`.

## Handoff

Complete this plan before `2026-10-11-local-headed-companion.md`. The first plan ships a usable local headless flow and a visibly unavailable hosted-headed option until the companion exists; it must never pretend a remote laptop browser is connected.

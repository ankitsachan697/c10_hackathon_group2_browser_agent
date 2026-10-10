# Local Headed Browser Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hosted backend can run a saved Playwright script against visible Chromium on the user's computer without exposing a local CDP port or executing generated Python on that computer.

**Architecture:** A small local companion launches Chromium and connects outbound to a paired backend WebSocket. The backend relays a single scoped CDP session to its isolated Playwright runner. Session selection is explicit per run, and loss of the companion yields an auditable `NEEDS_ATTENTION` outcome rather than a silent fallback.

**Tech Stack:** Python 3/FastAPI WebSockets/websockets/Playwright/SQLite/pytest; Next.js 16/React/Vitest.

**Spec:** `docs/superpowers/specs/2026-10-11-live-agent-journey-design.md`

**Prerequisite:** `2026-10-11-live-agent-journey.md` is complete and its headless first-run flow passes.

## Global Constraints

- No public Chrome debugging port; the companion connects outbound to the backend over TLS in hosted deployments.
- Generated Python and reusable credentials stay in the isolated backend runner, not the companion.
- Pairing uses a single-use short-lived code and a revocable, scoped device credential; secrets are never returned by public config or health routes.
- Headed execution requires an available selected companion and explicit user approval for that browser session.
- No silent fallback to server headless, raw CDP, or unsandboxed host Python when the companion disappears.
- Existing private `PLAYWRIGHT_CDP_ENDPOINT` remains an advanced, explicitly configured alternative.

## Review Focus

1. Expired/reused pairing code must fail without registering a device (Task 1 test).
2. Two users or runs race for one companion: only the approved session may attach (Task 2 test).
3. Relay disconnects mid-run: preserve events, close browser, and set `NEEDS_ATTENTION` (Task 3 test).
4. Backend sends a generated Python script or credential in a companion control message: reject by schema (Task 2 test).
5. Companion is offline at submit: UI blocks hosted headed selection with a clear explanation (Task 4 test).

## File Structure and Interfaces

- `backend/companion_registry.py`: device/pairing state and session authorization; no browser protocol parsing.
- `backend/cdp_relay.py`: byte-preserving WebSocket bridge between one runner connection and one companion connection.
- `backend/api/companions.py`: pairing, status, approval, and WebSocket endpoints; delegates storage/relay.
- `companion/browser_companion.py`: local CLI process; launches visible Chromium, connects outbound, heartbeats, and forwards CDP frames only.
- `backend/orchestrator.py`: selects `browser_target` and passes a scoped relay endpoint to the existing isolated runner.
- `frontend/components/browser/CompanionPicker.tsx`: device status and approval UX.

### Task 1: Pairing and Device Registry

**Files:** Create `backend/companion_registry.py`, `backend/api/companions.py`, `backend/tests/test_companion_registry.py`; modify `backend/database.py`, `backend/api/__init__.py`.

**Interfaces:** `CompanionRegistry.issue_pair_code(user_scope: str) -> dict`, `CompanionRegistry.exchange(code: str, device_name: str) -> dict`, `CompanionRegistry.heartbeat(device_id: str, credential: str) -> None`, `CompanionRegistry.list_online() -> list[dict]`, `CompanionRegistry.revoke(device_id: str) -> None`. API: create/exchange/list/revoke with authenticated admin/session boundary; no public anonymous pairing endpoint. Persist only a keyed hash of each device credential.

- [ ] **Step 1: Write failing tests** for 5-minute code expiry, one-time exchange, invalid/reused code, 30-second heartbeat online window, credential revocation, and private metadata in API responses.
- [ ] **Step 2: Run** `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_companion_registry.py -q`; expect failures.
- [ ] **Step 3: Implement** schema/registry/API. Require deployment authentication before issuing pair codes; if the app has no user auth, require an operator-supplied admin token and fail pairing when absent.
- [ ] **Step 4: Run** focused tests; expect pass.
- [ ] **Step 5: Commit** as `feat: pair local browser companions securely`.

### Task 2: Scoped CDP Relay and Local Companion

**Files:** Create `backend/cdp_relay.py`, `companion/browser_companion.py`, `backend/tests/test_cdp_relay.py`, `companion/tests/test_browser_companion.py`; modify `backend/api/companions.py`, `backend/requirements.txt` only if an additional dependency is required.

**Interfaces:** `CdpRelay.create_session(device_id: str, run_id: str, ttl_seconds: int = 90) -> RelaySession`, `CdpRelay.attach_companion(session_id, device_credential, websocket)`, `CdpRelay.attach_runner(session_id, runner_secret, websocket)`, `CdpRelay.close(session_id)`. Companion CLI: `python -m companion.browser_companion --server https://... --device-name ...`; obtains its credential by one-time pairing interaction, stores it with restrictive permissions, and opens only a loopback Chrome debugging socket.

- [ ] **Step 1: Write failing tests** for exact CDP message forwarding, one runner and one companion per session, wrong device/expired token rejection, no script/password fields in control-message schema, loopback-only Chrome endpoint, and relay cleanup.
- [ ] **Step 2: Run** relay/companion tests; expect failures.
- [ ] **Step 3: Implement** outbound companion WebSocket plus server bridge. Verify TLS outside explicit localhost development. Use bounded frame size, idle timeout, and no raw frame logging. The relay endpoint handed to Playwright is scoped and expires after the run.
- [ ] **Step 4: Run** focused tests; expect pass.
- [ ] **Step 5: Commit** as `feat: relay approved local browser sessions`.

### Task 3: Run Routing and Failure Semantics

**Files:** Modify `backend/orchestrator.py`, `backend/runner.py`, `backend/api/journeys.py`, `backend/api/runs.py`, `backend/tests/test_orchestrator.py`, `backend/tests/test_runner_remote_browser.py`.

**Interfaces:** `run_journey(..., browser_mode: str = "headless", companion_id: str | None = None)` uses the Task 2 relay only for hosted `headed` mode. `PlaywrightRunner.execute_script` receives a per-run CDP endpoint without changing global runner settings; `connect_over_cdp` remains the execution primitive.

- [ ] **Step 1: Write failing tests** for local headed propagation, hosted headed requiring an approved online companion, timeout/offline refusal, disconnect → `NEEDS_ATTENTION`, saved-script snapshot preservation, and no fallback to unsandboxed host execution.
- [ ] **Step 2: Run** focused orchestrator/runner tests; expect failures.
- [ ] **Step 3: Implement** per-run browser target and relay lifecycle. Ensure Docker worker can reach only the scoped backend relay endpoint, not the companion's loopback port. Close relay/browser in `finally`.
- [ ] **Step 4: Run** focused tests; expect pass.
- [ ] **Step 5: Commit** as `feat: route headed runs to paired browsers`.

### Task 4: Browser Selection and Pairing UX

**Files:** Create `frontend/components/browser/CompanionPicker.tsx`, `frontend/tests/companion-picker.test.tsx`; modify `frontend/components/journeys/JourneyForm.tsx`, `frontend/app/settings/page.tsx`, `frontend/app/runs/[id]/page.tsx`, `frontend/lib/types.ts`, `frontend/app/globals.css`.

**Interfaces:** `GET /api/companions` supplies non-secret availability; `POST /api/companions/{id}/approve-session` approves one run. The creation form offers `Headless` and `Watch in browser`; hosted headed selection names the device and shows pending approval before execution.

- [ ] **Step 1: Write failing component tests** for no-device disabled state, online device selection, approval confirmation, disconnect message, keyboard/focus behavior, and no bearer/pair credential in browser props.
- [ ] **Step 2: Run** `npm --prefix frontend test -- --run`; expect new tests to fail.
- [ ] **Step 3: Implement** device picker and pairing/status instructions. Link to the run's live events after approval.
- [ ] **Step 4: Run** frontend tests, lint, and build; expect pass.
- [ ] **Step 5: Commit** as `feat: select and monitor local headed browser`.

### Task 5: End-to-End Boundary and Documentation

**Files:** Create `backend/tests/test_companion_integration.py`; modify `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md`, `API_REFERENCE.md`, `.env.example`.

**Interfaces:** No new runtime API. Document pairing, TLS/reverse connectivity, local CLI launch, device revocation, and private CDP alternative.

- [ ] **Step 1: Write integration test** with fake companion WebSocket proving approve → relay → isolated runner → events/artifacts and a disconnect path preserving failure evidence.
- [ ] **Step 2: Run** integration test; expect failure until tasks 1–4 are fully connected.
- [ ] **Step 3: Update** deployment docs, secret setup, threat boundaries, and operator troubleshooting; do not claim that a remote server can reach a local browser without companion or private tunnel.
- [ ] **Step 4: Run** backend tests, frontend tests, lint, build, `git diff --check`, and a manual local headed browser probe; expect success before marking complete.
- [ ] **Step 5: Commit** as `docs: explain paired headed browser execution`.

# Live Verification Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn New Journey into a persistent prompt-to-evidence workspace with confirmed live Playwright actions and inline script, screenshot, recording, and visual results.

**Architecture:** Keep the existing generation, run, event, artifact, and rerun APIs. Reshape the Next.js page into configuration, live-session, and result components; share one cursor-based event hook for each scope so the stepper and console show the same recorded events. Preserve the Runs page as the rerun/history surface.

**Tech Stack:** Next.js 16.4, React 19, TypeScript, CSS, Vitest/Testing Library, FastAPI, Python Playwright, n8n.

**Spec:** `docs/superpowers/specs/2026-10-11-live-verification-workspace-design.md`

## Global Constraints

- Keep the Outskill black/charcoal and lime design, logo, responsive behavior, keyboard access, visible focus, and reduced-motion support.
- No Kane CLI, Vite migration, new execution path, target-specific selectors, hardcoded credentials, or new backend endpoints.
- Discovery alone uses n8n; saved-case, scheduled, on-demand, and rerun executions continue to use saved Playwright scripts.
- Operation `COMPLETED` is not a test-pass signal; run status determines the outcome.
- Planned discovery steps and confirmed browser action events are distinct; never infer an objective step passed from an action count.
- Credentials are masked, never rendered in logs, and cleared from the form only after accepted submission.

## Review Focus

1. Password-manager autofill without a React input event, followed by editing another field, must preserve the password until submission (Task 1 test).
2. A failed generation POST must leave the entered credentials available for retry without displaying them (Task 1 test).
3. A completed operation with a `NEEDS_ATTENTION` run must display failure/manual attention, not success (Task 2 test).
4. Repeated action names across attempts must remain distinguishable, without falsely mapping them to planned objective steps (Task 2 test).
5. Missing/deleted/unsupported media must show a fallback instead of a broken image or video (Task 3 test).

---

### Task 1: Prompt-first configuration page

**Files:**
- Modify: `frontend/components/journeys/JourneyForm.tsx`
- Modify: `frontend/app/globals.css`
- Test: `frontend/tests/journey-create.test.tsx`

**Interfaces:**
- Consumes: existing `POST /api/operations/generations`, `GenerationOperation`, `CompanionPicker`, `CreateProjectDialog`.
- Produces: `JourneyForm` still exported with no props; accepted submit still sets the operation ID and clears only the password DOM value. Task 2 and Task 3 extend its workspace below the configuration card.

- [ ] **Step 1: Write failing page tests.** Assert the objective is the dominant first input, the primary button is named `Verify & record live`, and project/name/URL/optional credential/browser-mode controls remain accessible. Retain the existing native autofill regression test. Add a rejected-POST test asserting the masked password input retains its value and an error is shown.
- [ ] **Step 2: Run the focused test.** Run: `cd frontend && npm test -- --run tests/journey-create.test.tsx`. Expected: the new prompt-first/button test fails before implementation.
- [ ] **Step 3: Implement the page.** Reorder and restyle `JourneyForm` as one page, with a large objective editor and a compact configuration section. Preserve existing project creation, password ref, idempotency key, validation, operation restoration, and headless/headed pairing. Set the CTA text and accessible name to `Verify & record live`; do not change the request payload or backend contract.
- [ ] **Step 4: Verify and commit.** Run: `cd frontend && npm test -- --run tests/journey-create.test.tsx`. Expected: all focused tests pass. Commit `JourneyForm.tsx`, CSS, and tests with message `feat: make journey entry prompt-first`.

### Task 2: Confirmed live progression and console

**Files:**
- Create: `frontend/components/runs/useActivityEvents.ts`
- Create: `frontend/components/runs/LiveRunProgress.tsx`
- Modify: `frontend/components/runs/RunActivity.tsx`
- Modify: `frontend/components/journeys/JourneyForm.tsx`
- Modify: `frontend/app/globals.css`
- Test: `frontend/tests/live-run-progress.test.tsx`
- Test: `frontend/tests/run-activity.test.tsx`

**Interfaces:**
- Consumes: Task 1 `JourneyForm`; `ActivityEvent` and `Run` from `frontend/lib/types.ts`; existing `GET /api/operations/{id}/events`, `GET /api/runs/{id}/events`, `GET /api/runs/{id}`.
- Produces: `useActivityEvents(scope: "run" | "operation", id?: string, terminal?: boolean): { events: ActivityEvent[]; error: string }` using a sequence cursor, deduplication, and a slower interval after terminal state; `LiveRunProgress({ operationEvents, runEvents, runStatus }: { operationEvents: ActivityEvent[]; runEvents: ActivityEvent[]; runStatus?: string })` renders planned discovery separately from actual action progression and a selectable console. Task 3 consumes the same `runEvents` array and `Run` state from `JourneyForm`.

- [ ] **Step 1: Write failing live-state tests.** Feed `generation.completed` with `discovered_steps`, two attempts containing the same `fill` action, and a final `NEEDS_ATTENTION` run. Assert planned steps are labeled planned, attempt/action statuses derive only from recorded action events, the console shows redacted event messages, and no success heading appears. Test the event hook's `after_seq` cursor, deduplication, reset when scope ID changes, and slower terminal-state polling.
- [ ] **Step 2: Run focused tests.** Run: `cd frontend && npm test -- --run tests/live-run-progress.test.tsx tests/run-activity.test.tsx`. Expected: new tests fail because the hook/component do not exist.
- [ ] **Step 3: Implement event and live components.** Extract `RunActivity` polling into the hook; render the live stepper and console from its returned events. Poll run detail while active and use `run.status` for the outcome; operation status only describes generation. In `JourneyForm`, obtain one operation feed and one run feed, pass them into `LiveRunProgress`, and recover them from the stored operation ID after refresh. Keep raw event text escaped by React and never show credential values.
- [ ] **Step 4: Verify and commit.** Run: `cd frontend && npm test -- --run tests/live-run-progress.test.tsx tests/run-activity.test.tsx tests/journey-create.test.tsx`. Expected: all focused tests pass. Commit the components, CSS, and tests with message `feat: show confirmed browser progression and console`.

### Task 3: Inline evidence tabs and Runs reuse

**Files:**
- Create: `frontend/components/runs/RunResultTabs.tsx`
- Create: `frontend/components/runs/RunMedia.tsx`
- Modify: `frontend/components/runs/RunEvidence.tsx`
- Modify: `frontend/components/journeys/JourneyForm.tsx`
- Modify: `frontend/app/runs/[id]/page.tsx`
- Modify: `frontend/app/globals.css`
- Test: `frontend/tests/run-result-tabs.test.tsx`
- Test: `frontend/tests/run-detail.test.tsx`
- Test: `frontend/tests/journey-create.test.tsx`

**Interfaces:**
- Consumes: Task 2 `runEvents: ActivityEvent[]` and current `Run` state in `JourneyForm`; existing `RunScript`, `RunVisual`, `RunActivity`, artifact route, and rerun API.
- Produces: `RunResultTabs({ run, runEvents }: { run: Run; runEvents: ActivityEvent[] })` with Steps & Logs, Playwright Script, Screenshots, Recording, and Visual tabs; `RunMedia({ artifacts, kind }: { artifacts: Artifact[]; kind: "screenshot" | "video" })` with inline previews and open links. The run detail page uses the same media presentation and preserves Repair, rerun, and delete controls.

- [ ] **Step 1: Write failing evidence tests.** Assert screenshot cards render images, recordings render `<video controls>`, script and visual content are reachable by keyboard-accessible tabs, missing/deleted/unsupported media has an explicit fallback, and a `NEEDS_ATTENTION` run still exposes available evidence. In run-detail tests assert both rerun modes still POST to `/rerun` and the new screenshot/recording tabs appear.
- [ ] **Step 2: Run focused tests.** Run: `cd frontend && npm test -- --run tests/run-result-tabs.test.tsx tests/run-detail.test.tsx tests/journey-create.test.tsx`. Expected: new component/tab assertions fail before implementation.
- [ ] **Step 3: Implement tabs and media.** Use the proxied `/api/artifacts/{id}` route for inline media, enforce artifact kind/media type, and provide open links plus loading/empty/error fallbacks. Wire `JourneyForm` to fetch the run and refresh artifacts while it runs; show `RunResultTabs` as soon as a run exists. Reuse the media component on run detail, keeping its existing repair, visual, rerun, and delete actions.
- [ ] **Step 4: Run full verification.** Run: `cd frontend && npm test -- --run`, `cd frontend && npm run lint`, `cd frontend && npm run build`, and `backend/.venv/bin/python -m pytest backend/tests -q`. Expected: all pass. Walk through the new page and an existing saved run in a browser using Playwright/MCP, confirm tabs and evidence without launching a new n8n job, and note any environment-limited behavior.
- [ ] **Step 5: Commit.** Commit the page, components, CSS, and tests with message `feat: show run script and evidence in verification workspace`.

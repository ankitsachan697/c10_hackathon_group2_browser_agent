# Browser Automation Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a polished Outskill-branded browser automation control center that executes saved Playwright scripts on demand or daily, performs at most one eligible automatic repair retry, and preserves a clear audit trail.

**Architecture:** FastAPI owns a SQLite-backed resource model, orchestration state machine, artifact lifecycle, and restart-safe daily scheduler. Next.js consumes typed resource APIs through focused Overview, Projects, Runs, Schedules, and Settings views. n8n is invoked only for explicit journey generation and eligible failed-run repair; normal saved-script executions remain deterministic.

**Tech Stack:** Python 3.10+, FastAPI, stdlib SQLite, APScheduler, Pydantic 2, pytest, Next.js 16, React 19, TypeScript, Tailwind CSS 4, Vitest, Testing Library, Playwright runner, n8n MCP.

**Spec:** `docs/superpowers/specs/2026-10-10-browser-automation-studio-design.md`

## Global Constraints

- Scheduled, on-demand, saved-case, project, and rerun paths execute saved Playwright scripts and never invoke discovery/script generation.
- Exactly one eligible automatic repair and verification retry is permitted.
- A second failure ends in `NEEDS_ATTENTION` and retains both attempts.
- Passing saved-script runs make no LLM call.
- No secrets, real credentials, integration endpoints, demo URLs, branding values, thresholds, timeouts, or retry counts are hardcoded into product behavior.
- The interface uses Outskill branding and contains no “enterprise” marketing copy.
- Existing JSON cases and run history must remain importable.
- Use the existing filesystem artifact store through stable database records; recoverable deletion moves files to trash.

## Review Focus

- Concurrent Run now and scheduler triggers for the same scope must produce one execution and one explicit overlap rejection.
- DST and invalid timezone inputs must calculate a valid next run or return a validation error without silently shifting schedules.
- Missing/corrupt legacy JSON must not prevent first startup or create duplicate imports.
- Paths containing traversal segments must never escape the configured artifact root during serve, trash, or restore operations.
- n8n timeout, malformed JSON, or oversized failure context must end in a useful manual-attention state without leaking secrets.

---

## File Structure

### Backend

- `backend/config.py`: environment-backed typed settings.
- `backend/database.py`: SQLite connection, schema, transactions, and migration marker.
- `backend/models.py`: enums and API/domain Pydantic models.
- `backend/repositories.py`: project, journey, schedule, run, environment, and artifact persistence.
- `backend/legacy_import.py`: idempotent JSON import.
- `backend/failure_context.py`: redaction, deterministic eligibility, and bounded repair packets.
- `backend/orchestrator.py`: one execution state machine for every trigger.
- `backend/scheduler.py`: APScheduler adapter and overlap control.
- `backend/artifact_store.py`: root-safe artifact addressing and recoverable trash.
- `backend/server.py`: composition and HTTP routes only.
- `backend/n8n_client.py`: configured agent gateway with strict request/response boundaries.

### Frontend

- `frontend/lib/api.ts`: typed API client and error normalization.
- `frontend/lib/types.ts`: shared client resource types.
- `frontend/components/ui/Button.tsx`, `StatusBadge.tsx`, `Card.tsx`, `ConfirmDialog.tsx`, `ActionMenu.tsx`, `DataTable.tsx`, `EmptyState.tsx`, and `ToastProvider.tsx`: shared interaction primitives.
- `frontend/components/shell/AppShell.tsx`, `Sidebar.tsx`, and `Header.tsx`: branded responsive navigation and health shell.
- `frontend/components/runs/RunTimeline.tsx`, `RunEvidence.tsx`, `RunScript.tsx`, `RunRepair.tsx`, `RunLogs.tsx`, and `RunVisual.tsx`: audited run detail panels.
- `frontend/app/page.tsx`: Overview route.
- `frontend/app/projects/page.tsx`: Projects route.
- `frontend/app/runs/page.tsx`: Runs route.
- `frontend/app/runs/[id]/page.tsx`: Run detail route.
- `frontend/app/schedules/page.tsx`: Schedules route.
- `frontend/app/settings/page.tsx`: Settings route.
- `frontend/public/outskill-logo.svg` and `frontend/public/outskill-mark.png`: copied approved assets from `xray_lens`.

---

### Task 1: Secure Configuration and Test Harness

**Files:**
- Create: `backend/config.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_config.py`
- Modify: `backend/n8n_client.py`
- Modify: `backend/server.py`
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `Settings.from_env() -> Settings`; configured `N8nClient(settings: Settings)`.
- Consumes: environment variables only; no committed token or fixed n8n endpoint fallback.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_settings_do_not_supply_a_secret_token(monkeypatch):
    monkeypatch.delenv("N8N_BEARER_TOKEN", raising=False)
    assert Settings.from_env().n8n_bearer_token is None

def test_retry_limit_is_exactly_one(monkeypatch):
    monkeypatch.setenv("AUTO_REPAIR_RETRIES", "7")
    assert Settings.from_env().auto_repair_retries == 1
```

- [ ] **Step 2: Run `python3 -m pytest backend/tests/test_config.py -q` and verify it fails because `backend.config` does not exist.**
- [ ] **Step 3: Implement immutable settings for database/artifact paths, branding, CORS, runner timeout, visual threshold, scheduler timezone, n8n endpoint/token/model limits, and feature flags. Remove the committed bearer token, fixed credential ID, and unconditional `n8n_connected: True`.**
- [ ] **Step 4: Add pytest, pytest-asyncio, APScheduler, httpx, Vitest, jsdom, and Testing Library dependencies plus backend/frontend test scripts. Ignore runtime database, environment, coverage, trash, and test-output files.**
- [ ] **Step 5: Run the focused tests and `rg -n 'eyJ[a-zA-Z0-9_-]+\.' backend n8n_workflows frontend`; expect tests to pass and no bearer token match.**
- [ ] **Step 6: Commit with `git commit -m "chore: secure runtime configuration"`.**

### Task 2: SQLite Domain Store and Legacy Import

**Files:**
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/repositories.py`
- Create: `backend/legacy_import.py`
- Create: `backend/tests/test_repositories.py`
- Create: `backend/tests/test_legacy_import.py`
- Modify: `backend/test_suite_manager.py`

**Interfaces:**
- Produces: `Database.transaction()`, `ProjectRepository`, `JourneyRepository`, `ScheduleRepository`, `RunRepository`, `EnvironmentRepository`, `ArtifactRepository`, and `import_legacy_json(database, cases_path, runs_path) -> ImportSummary`.
- Consumes: `Settings.database_path`, existing `cases.json`, and `runs_history.json`.

- [ ] **Step 1: Write failing repository tests for CRUD, stable IDs, immutable run script snapshots, transactional project cascade deletion, and schedule/run relationships.**
- [ ] **Step 2: Write failing import tests asserting missing/corrupt input is non-fatal and rerunning import creates no duplicates.**
- [ ] **Step 3: Run `python3 -m pytest backend/tests/test_repositories.py backend/tests/test_legacy_import.py -q`; expect import errors.**
- [ ] **Step 4: Implement schema versioning and repositories for projects, journeys, schedules, runs, attempts, environments, artifacts, and import markers. Use foreign keys and explicit transactions.**
- [ ] **Step 5: Implement idempotent legacy mapping: each unique legacy `project` becomes a Project, each case becomes a Journey, and each history item becomes a Run with best-effort linkage. Keep `test_suite_manager.py` as a compatibility adapter during migration.**
- [ ] **Step 6: Run the focused tests twice against the same temporary database; expect identical counts and all tests passing.**
- [ ] **Step 7: Commit with `git commit -m "feat: add durable project and run store"`.**

### Task 3: Safe Artifact Lifecycle and Compact Failure Context

**Files:**
- Create: `backend/artifact_store.py`
- Create: `backend/failure_context.py`
- Create: `backend/tests/test_artifact_store.py`
- Create: `backend/tests/test_failure_context.py`
- Modify: `backend/runner.py`

**Interfaces:**
- Produces: `ArtifactStore.resolve(id)`, `ArtifactStore.trash_run(run_id)`, `classify_failure(result) -> FailureDecision`, and `build_failure_packet(result, limits) -> FailurePacket`.
- Consumes: runner output and configured artifact/trash roots.

- [ ] **Step 1: Write failing tests that reject `../` traversal, move run artifacts to trash, preserve metadata, redact supplied secrets, cap traceback/DOM size, and exclude videos/full DOM from repair packets.**
- [ ] **Step 2: Add failure eligibility tests for broken selectors/timeouts versus authentication, infrastructure, and assertion failures.**
- [ ] **Step 3: Run the focused test files and verify failures.**
- [ ] **Step 4: Implement root-safe artifact operations and deterministic failure classification/compaction. Update runner results to expose structured failed action, locator evidence, bounded DOM excerpt, and artifact references.**
- [ ] **Step 5: Run focused tests and `python3 -m pytest backend/tests -q`; expect all current backend tests to pass.**
- [ ] **Step 6: Commit with `git commit -m "feat: add safe evidence and failure packets"`.**

### Task 4: Unified Saved-Script Orchestration

**Files:**
- Create: `backend/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`
- Modify: `backend/n8n_client.py`
- Modify: `backend/server.py`

**Interfaces:**
- Produces: `RunOrchestrator.run_journey(journey_id, trigger, script_version=None) -> Run`; `RunOrchestrator.run_project(project_id, trigger) -> list[Run]`.
- Consumes: repositories, runner, failure classifier, artifact store, and `N8nClient.diagnose_and_repair(packet)`.

- [ ] **Step 1: Write failing async tests proving scheduled/on-demand/saved/project/rerun triggers call the runner with saved scripts and never call generation.**
- [ ] **Step 2: Add tests proving a pass uses zero n8n calls, an eligible failure uses one repair call and one retry, a repaired pass records `PASSED_AFTER_REPAIR`, and a second failure records `NEEDS_ATTENTION`.**
- [ ] **Step 3: Add tests for ineligible failures, n8n timeout/malformed response, redacted prompt data, and historical current-script versus snapshot reruns.**
- [ ] **Step 4: Run `python3 -m pytest backend/tests/test_orchestrator.py -q`; expect failures.**
- [ ] **Step 5: Implement the state machine and strict n8n repair response model. Change n8n repair to accept only the compact failure packet; retain the deterministic local fallback behind a feature flag and label its source accurately.**
- [ ] **Step 6: Remove or adapt `/api/autonomous-run` so no operational route regenerates scripts. Keep generation behind explicit create/regenerate commands only.**
- [ ] **Step 7: Run focused and full backend tests; expect one-retry and no-generation assertions to pass.**
- [ ] **Step 8: Commit with `git commit -m "feat: unify saved-script run orchestration"`.**

### Task 5: Restart-Safe Daily Scheduler

**Files:**
- Create: `backend/scheduler.py`
- Create: `backend/tests/test_scheduler.py`
- Modify: `backend/server.py`
- Modify: `backend/models.py`

**Interfaces:**
- Produces: `ScheduleService.create_daily(...)`, `update(...)`, `delete(...)`, `run_now(id)`, `restore_enabled()`, and `next_run(schedule, now) -> datetime`.
- Consumes: schedule repository and run orchestrator.

- [ ] **Step 1: Write failing tests for `Asia/Kolkata` next-run calculation, DST boundaries, invalid timezone rejection, enable/disable, restart restoration, and missed-run reconciliation.**
- [ ] **Step 2: Add a concurrency test where scheduler and Run now target the same scope; assert one execution and one explicit overlap result.**
- [ ] **Step 3: Run `python3 -m pytest backend/tests/test_scheduler.py -q`; expect failures.**
- [ ] **Step 4: Implement an APScheduler adapter with persistent schedules stored in SQLite, one application scheduler process, per-scope async locks, coalescing, and no duplicate catch-up executions.**
- [ ] **Step 5: Wire scheduler startup/shutdown through FastAPI lifespan and expose actual scheduler health.**
- [ ] **Step 6: Run scheduler tests with fixed clocks and then the full backend suite.**
- [ ] **Step 7: Commit with `git commit -m "feat: schedule daily regression runs"`.**

### Task 6: Resource and Lifecycle APIs

**Files:**
- Create: `backend/api/projects.py`
- Create: `backend/api/journeys.py`
- Create: `backend/api/runs.py`
- Create: `backend/api/schedules.py`
- Create: `backend/api/environments.py`
- Create: `backend/api/system.py`
- Create: `backend/tests/test_api.py`
- Modify: `backend/server.py`

**Interfaces:**
- Produces: resource CRUD plus project/journey/schedule Run now, historical current/snapshot rerun, explicit generate/regenerate, deletion impact preview, and consistent `{data, error, meta}` envelopes.
- Consumes: repositories, orchestrator, scheduler, artifact store, and configured n8n client.

- [ ] **Step 1: Write failing API tests for CRUD validation, pagination/filtering, all Run now routes, rerun modes, explicit generation boundaries, deletion preview/cascade, artifact trash, and structured errors.**
- [ ] **Step 2: Add API tests asserting no operational endpoint calls generation and path traversal returns 404/validation failure.**
- [ ] **Step 3: Run `python3 -m pytest backend/tests/test_api.py -q`; expect missing-route failures.**
- [ ] **Step 4: Split routers from server composition, implement request/response models, preserve temporary compatibility endpoints, and replace hardcoded CORS/health values with settings and probes.**
- [ ] **Step 5: Run all backend tests and inspect generated OpenAPI for duplicated or ambiguous operations.**
- [ ] **Step 6: Commit with `git commit -m "feat: expose browser automation resource APIs"`.**

### Task 7: Outskill-Branded Application Shell and Core Views

**Files:**
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/components/ui/Button.tsx`
- Create: `frontend/components/ui/StatusBadge.tsx`
- Create: `frontend/components/ui/Card.tsx`
- Create: `frontend/components/ui/ConfirmDialog.tsx`
- Create: `frontend/components/ui/ActionMenu.tsx`
- Create: `frontend/components/ui/DataTable.tsx`
- Create: `frontend/components/ui/EmptyState.tsx`
- Create: `frontend/components/ui/ToastProvider.tsx`
- Create: `frontend/components/shell/AppShell.tsx`
- Create: `frontend/components/shell/Sidebar.tsx`
- Create: `frontend/components/shell/Header.tsx`
- Create: `frontend/app/projects/page.tsx`
- Create: `frontend/app/runs/page.tsx`
- Create: `frontend/app/schedules/page.tsx`
- Create: `frontend/app/settings/page.tsx`
- Create: `frontend/tests/shell.test.tsx`
- Create: `frontend/tests/projects.test.tsx`
- Create: `frontend/tests/schedules.test.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`
- Copy: `xray_lens/frontend/public/full_logo.svg` to `frontend/public/outskill-logo.svg`
- Copy: `xray_lens/frontend/public/mini_logo.png` to `frontend/public/outskill-mark.png`

**Interfaces:**
- Produces: typed `api` client, responsive `AppShell`, Overview, Projects, Runs, Schedules, and Settings views.
- Consumes: Task 6 response contracts and public runtime configuration.

- [ ] **Step 1: Write failing component tests for navigation, service health, loading/error/empty states, project Run now/delete confirmation, schedule timezone fields, enable toggle, and Run now.**
- [ ] **Step 2: Run `npm test -- --run` from `frontend`; expect missing-component failures.**
- [ ] **Step 3: Add theme tokens, accessible UI primitives, branded responsive shell, health header, toast provider, and reduced-motion/focus styles.**
- [ ] **Step 4: Replace the monolithic dashboard with focused views and typed API calls. Use tables on wide screens and readable cards on narrow screens; place secondary actions in contextual menus.**
- [ ] **Step 5: Implement deletion impact dialogs, search/filter/sort controls, daily schedule form, Run now actions, and user-facing API error messages.**
- [ ] **Step 6: Run frontend tests, `npm run lint`, and `npm run build`; expect all to pass.**
- [ ] **Step 7: Commit with `git commit -m "feat: redesign browser automation workspace"`.**

### Task 8: Journey Creation and Run Detail Experience

**Files:**
- Create: `frontend/app/journeys/new/page.tsx`
- Create: `frontend/app/runs/[id]/page.tsx`
- Create: `frontend/components/runs/RunTimeline.tsx`
- Create: `frontend/components/runs/RunEvidence.tsx`
- Create: `frontend/components/runs/RunScript.tsx`
- Create: `frontend/components/runs/RunRepair.tsx`
- Create: `frontend/components/runs/RunLogs.tsx`
- Create: `frontend/components/runs/RunVisual.tsx`
- Create: `frontend/tests/journey-create.test.tsx`
- Create: `frontend/tests/run-detail.test.tsx`
- Modify: `frontend/components/ScriptDiffViewer.tsx`
- Modify: `frontend/components/VisualRegressionViewer.tsx`
- Modify: `frontend/components/LiveLogTerminal.tsx`

**Interfaces:**
- Produces: guided explicit-generation flow and audited Run Detail experience.
- Consumes: journey generation endpoint, run/attempt/artifact APIs, and typed resource models.

- [ ] **Step 1: Write failing tests proving generation occurs only after explicit journey submission/regeneration and never from Run now.**
- [ ] **Step 2: Add run-detail tests for timeline states, Passed after repair, Needs attention, evidence tabs, repair diff, current-script rerun, snapshot rerun, and run deletion.**
- [ ] **Step 3: Run focused frontend tests; expect failures.**
- [ ] **Step 4: Implement the guided creation flow with project/environment selection, URL/objective, browser settings, review, generated script validation, and save.**
- [ ] **Step 5: Implement run timeline and Evidence, Script, Repair, Logs, and Visual tabs; reuse the existing specialized viewers after adapting them to typed artifact IDs.**
- [ ] **Step 6: Run all frontend tests, lint, and production build.**
- [ ] **Step 7: Commit with `git commit -m "feat: add journey and run detail workflows"`.**

### Task 9: n8n Workflow Hardening and Documentation

**Files:**
- Modify: `n8n_workflows/flow_discovery_and_generator.json`
- Modify: `n8n_workflows/error_diagnosis_and_repair.json`
- Modify: `n8n_workflows/visual_regression_monitor.json`
- Modify: `n8n_workflows/deploy_workflows.py`
- Modify: `N8N_AGENTS.md`
- Modify: `API_REFERENCE.md`
- Modify: `ARCHITECTURE.md`
- Modify: `README.md`
- Create: `.env.example`

**Interfaces:**
- Produces: strict JSON generation/repair contracts and token-bounded deployment configuration.
- Consumes: compact failure packet and explicit generation request schemas.

- [ ] **Step 1: Add JSON-schema validation tests or a validation script for workflow names, webhook contracts, model settings, output parsability, and absence of secrets.**
- [ ] **Step 2: Make model name, maximum tokens, temperature, agent IDs, and endpoints deployment-configured; narrow repair input to bounded fields and remove the no-op visual n8n workflow from the runtime path.**
- [ ] **Step 3: Update docs to match actual model/configuration and saved-script execution behavior; remove stale “enterprise” wording and obsolete absolute paths.**
- [ ] **Step 4: Run workflow validation, secret scan, backend tests, frontend tests, lint, and build.**
- [ ] **Step 5: Commit with `git commit -m "chore: harden agent workflow contracts"`.**

### Task 10: Full-System Verification and Browser Acceptance

**Files:**
- Create through Kane CLI assurance: `tests/browser/browser_automation_studio_test.md`
- Modify only if failures require scoped fixes: affected backend/frontend files and tests.

**Interfaces:**
- Produces: requirement-linked browser acceptance coverage and final verification evidence.
- Consumes: the approved design, running backend, running frontend, and demo fixtures supplied through environment configuration.

- [ ] **Step 1: Use Kane CLI assurance against the design spec to generate requirement-linked cases for create journey, saved-script Run now, daily schedule, repair success, retry failure, historical rerun, and deletion. Do not hand-write browser cases.**
- [ ] **Step 2: Start backend/frontend with isolated test database and artifact roots; execute the generated critical suite with `kane-cli ... --agent`.**
- [ ] **Step 3: Fix only evidence-backed failures using the systematic-debugging workflow, rerunning the smallest relevant test first.**
- [ ] **Step 4: Run final verification:**

```bash
python3 -m pytest backend/tests -q
cd frontend && npm test -- --run
cd frontend && npm run lint
cd frontend && npm run build
rg -n 'eyJ[a-zA-Z0-9_-]+\.|Password123|practicetestautomation\.com|enterprise' backend frontend n8n_workflows README.md ARCHITECTURE.md N8N_AGENTS.md
git diff --check
```

Expected: all test/build commands pass; search reports no bearer tokens, hardcoded demo credentials/URLs, or prohibited product copy except explicitly documented migration fixtures where justified.

- [ ] **Step 5: Review keyboard navigation, visible focus, dialog names, responsive layouts, empty states, and reduced motion in the browser evidence.**
- [ ] **Step 6: Commit final scoped fixes with `git commit -m "test: verify browser automation studio"`.**

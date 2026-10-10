# Journey Onboarding, Credentials, and Runtime Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make first-time journey creation usable, remove fragile browser-to-backend configuration, securely persist reusable journey credentials, and verify the approved login journey with complete run evidence.

**Architecture:** Safe defaults and non-secret integration values live in tracked JSON with environment overrides; only bearer and encryption keys remain runtime secrets. Next.js proxies same-origin API requests to FastAPI. FastAPI stores authenticated ciphertext for journey credentials and decrypts it only when constructing the isolated runner environment for any execution trigger.

**Tech Stack:** Python 3, FastAPI, SQLite, `cryptography` Fernet, Playwright Python, Next.js 16, React 19, TypeScript, Vitest, Playwright Test, GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-10-10-browser-automation-studio-design.md`

## Global Constraints

- Saved, scheduled, project, and rerun execution must run the saved Playwright script directly.
- Agents are limited to explicit generation and one eligible diagnosis/repair retry.
- Secrets must never be committed, returned by APIs, embedded in scripts, logged, or sent to n8n.
- Product copy must not use “enterprise”; Outskill branding remains intact.
- Exactly one repair retry remains the maximum.
- Existing databases must migrate in place without losing projects, journeys, schedules, runs, or artifacts.

## Review Focus

- An empty project list must offer project creation without losing partially entered journey data; Task 5 adds a component test.
- A backend outage must produce a retryable error state rather than an unhandled promise rejection; Task 4 adds transport-failure tests.
- A missing or incorrect encryption key must fail safely without deleting or exposing credentials; Task 2 adds vault and API tests.
- Project, scheduled, current-script, and snapshot reruns must all receive the same decrypted credentials; Task 3 adds orchestration tests.
- Plaintext username/password must not appear in SQLite, API responses, scripts, logs, or repair packets; Tasks 2, 3, and 6 add explicit assertions.

---

### Task 1: Tracked Non-Secret Application Configuration

**Files:**
- Create: `config/application.json`
- Modify: `backend/config.py`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_configuration_wiring.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `load_application_config(path: Path | None = None) -> dict[str, Any]` and `Settings.from_env()` precedence of environment override → tracked JSON → safe default.
- Produces: settings for n8n endpoint/agent IDs/flags, backend internal URL, scheduler, runner, and visual defaults; secret fields remain environment-only.

- [ ] **Step 1: Write failing configuration tests** asserting tracked n8n values load without environment variables, environment variables override tracked values, and neither bearer token nor credential key can be sourced from JSON.
- [ ] **Step 2: Run `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_config.py backend/tests/test_configuration_wiring.py -q`** and verify the new tests fail.
- [ ] **Step 3: Add `config/application.json` and implement `load_application_config()` plus typed fallback/override mapping in `backend/config.py`.**
- [ ] **Step 4: Reduce `.env.example` to secrets and machine/deployment overrides, with comments pointing to tracked JSON.**
- [ ] **Step 5: Run the focused tests and verify they pass.**
- [ ] **Step 6: Commit with `feat: add tracked application configuration`.**

### Task 2: Authenticated Journey Credential Storage

**Files:**
- Create: `backend/credential_vault.py`
- Create: `backend/tests/test_credential_vault.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/database.py`
- Modify: `backend/repositories.py`
- Modify: `backend/tests/test_repositories.py`

**Interfaces:**
- Produces: `CredentialVault.encrypt(username: str, password: str) -> str` and `CredentialVault.decrypt(ciphertext: str) -> tuple[str, str]` using `CREDENTIAL_ENCRYPTION_KEY`.
- Produces: nullable `credential_ciphertext` and `has_credentials` journey persistence fields; public repository/API projections never contain ciphertext or plaintext.

- [ ] **Step 1: Add failing vault tests** for round-trip, randomized ciphertext, missing key, invalid key, tampered ciphertext, and no plaintext substrings in the stored value.
- [ ] **Step 2: Add failing repository migration tests** proving an existing schema upgrades in place and public journey reads expose only `has_credentials`.
- [ ] **Step 3: Run the focused backend tests and verify the expected failures.**
- [ ] **Step 4: Add a pinned-compatible `cryptography` dependency and implement the vault with Fernet authenticated encryption.**
- [ ] **Step 5: Add an idempotent schema migration and private repository methods for setting/retrieving credential ciphertext.**
- [ ] **Step 6: Run vault and repository tests and verify they pass.**
- [ ] **Step 7: Commit with `feat: encrypt reusable journey credentials`.**

### Task 3: Secure Generation and Every-Trigger Credential Injection

**Files:**
- Modify: `backend/api/context.py`
- Modify: `backend/api/journeys.py`
- Modify: `backend/orchestrator.py`
- Modify: `backend/runner.py`
- Modify: `backend/server.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_orchestrator.py`
- Modify: `backend/tests/test_runner_remote_browser.py`

**Interfaces:**
- Consumes: `CredentialVault`, private journey ciphertext access, and `has_credentials` from Task 2.
- Produces: journey create/generate inputs `username?: str`, `password?: str`; runner call `execute_script(..., env_vars: dict[str, str] | None = None, secrets: Iterable[str] = ())`.
- Produces: generated scripts use `AUTH_USERNAME` and `AUTH_PASSWORD`; n8n receives only `credentials_meta={"has_auth": bool}`.

- [ ] **Step 1: Add failing API tests** proving credentials can be submitted, are absent from responses and saved scripts, and n8n receives metadata rather than values.
- [ ] **Step 2: Add failing orchestrator tests** for on-demand, scheduled, project, current rerun, snapshot rerun, and repair retry environment injection.
- [ ] **Step 3: Add failing redaction tests** proving runner stdout/stderr and failure context cannot contain either credential.
- [ ] **Step 4: Run the focused tests and verify they fail for the missing interfaces.**
- [ ] **Step 5: Wire the vault through `AppServices`, journey endpoints, orchestration, and the runner’s minimal worker environment.**
- [ ] **Step 6: Ensure decryption occurs immediately before execution and secrets are discarded from application data after the call.**
- [ ] **Step 7: Run focused API/orchestrator/runner tests and verify they pass.**
- [ ] **Step 8: Commit with `feat: inject journey credentials into saved runs`.**

### Task 4: Same-Origin API Proxy and Recoverable Connectivity Errors

**Files:**
- Modify: `frontend/next.config.ts`
- Modify: `frontend/lib/api.ts`
- Create: `frontend/tests/api.test.ts`
- Modify: `frontend/components/shell/Header.tsx`
- Modify: `frontend/tests/shell.test.tsx`

**Interfaces:**
- Consumes: tracked `backend.internalUrl` from Task 1.
- Produces: browser API base `""` with `/api/:path*` rewritten server-side; `ApiTransportError` carries a safe message and retry eligibility.

- [ ] **Step 1: Add failing API client tests** for same-origin paths, malformed/non-JSON responses, network rejection, and structured backend errors.
- [ ] **Step 2: Add a failing shell test** asserting unavailable health is labeled accurately without throwing.
- [ ] **Step 3: Run the focused frontend tests and verify they fail.**
- [ ] **Step 4: Configure the Next.js rewrite from tracked JSON and remove the normal dependency on `NEXT_PUBLIC_BACKEND_URL`.**
- [ ] **Step 5: Normalize transport errors in `api()` and update health rendering with actionable, secret-free states.**
- [ ] **Step 6: Run focused tests, lint, and a production build; verify all pass.**
- [ ] **Step 7: Commit with `fix: proxy backend requests and handle outages`.**

### Task 5: First-Project and Credential-Aware Journey Wizard

**Files:**
- Create: `frontend/components/projects/CreateProjectDialog.tsx`
- Modify: `frontend/app/journeys/new/page.tsx`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/tests/journey-create.test.tsx`
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Consumes: `POST /api/projects`, journey credential inputs from Task 3, and transport errors from Task 4.
- Produces: accessible create-project dialog with `onCreated(project: Project): void`; masked password with explicit visibility toggle; retryable project-load state.

- [ ] **Step 1: Add failing tests** for empty-list Create first project, selector New project, modal validation, automatic selection, and preservation of entered journey fields.
- [ ] **Step 2: Add failing tests** for masked password, visibility toggle, credential review masking, and credential submission outside the objective text.
- [ ] **Step 3: Add a failing test** for a project-load network error followed by successful Retry.
- [ ] **Step 4: Run `npm --prefix frontend test -- --run tests/journey-create.test.tsx` and verify failures.**
- [ ] **Step 5: Implement the focused dialog and refactor the wizard into readable state handlers while preserving its three-step confirmation flow.**
- [ ] **Step 6: Apply Outskill-consistent responsive styling and keyboard/focus behavior.**
- [ ] **Step 7: Run focused tests, lint, and build and verify they pass.**
- [ ] **Step 8: Commit with `feat: complete first-time journey onboarding`.**

### Task 6: Login Acceptance, Evidence Assurance, CI Secrets, and Documentation

**Files:**
- Modify: `frontend/tests/browser/browser-automation-studio.spec.ts`
- Modify: `backend/tests/test_orchestrator.py`
- Create: `.github/workflows/quality.yml`
- Modify: `README.md`
- Modify: `USER_GUIDE.md`
- Modify: `API_REFERENCE.md`

**Interfaces:**
- Consumes: all preceding tasks.
- Produces: CI quality workflow with runtime mappings for `N8N_BEARER_TOKEN` and `CREDENTIAL_ENCRYPTION_KEY`; documented local/GitHub/deployed configuration boundaries.

- [ ] **Step 1: Extend backend evidence tests** to assert screenshots, flushed video, logs, attempts, and immutable script snapshots are registered without credential leakage.
- [ ] **Step 2: Add a browser acceptance test** that creates its first project in the wizard, supplies `student` / `Password123`, targets `https://practicetestautomation.com/practice-test-login/`, generates/saves the journey, executes it, and validates `Logged In Successfully` plus run evidence.
- [ ] **Step 3: Run the new tests and verify any missing behavior fails before final implementation adjustments.**
- [ ] **Step 4: Add `.github/workflows/quality.yml`** for backend tests, frontend tests/lint/build, workflow validation, and secret-to-runtime mappings without echoing secret values.
- [ ] **Step 5: Update documentation** with tracked JSON settings, the two runtime secrets, key generation, local startup, GitHub Secrets, deployment injection, credential replacement, and evidence behavior.
- [ ] **Step 6: Run the full backend suite, frontend suite, lint, production build, n8n contract validation, and browser acceptance suite.**
- [ ] **Step 7: Run `git diff --check` and a tracked-secret scan; verify no token, password, plaintext credential, or generated runtime database is committed.**
- [ ] **Step 8: Commit with `test: verify secure login journey end to end`.**
- [ ] **Step 9: Push `codex/browser-studio-redesign`, update the attached pull request, and perform a final whole-branch review.**

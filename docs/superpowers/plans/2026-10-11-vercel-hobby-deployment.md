# Vercel Hobby Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy and verify a fresh, protected Group2 Studio on the approved free Vercel account, using real n8n agents and isolated Playwright workers.

**Architecture:** Next.js Functions bootstrap and proxy one trusted persistent FastAPI control Sandbox per environment. Separate ephemeral Sandboxes inspect targets and execute generated scripts; SQLite, its credential key, and bounded private artifacts stay in the controller. Preserve local Docker execution and never substitute an unisolated subprocess for cloud execution.

**Tech Stack:** Existing Next.js 16.4/React/TypeScript, Python/FastAPI/SQLite/Playwright, Vercel Sandbox SDK, GitHub Actions, and existing n8n Cloud agents. Select compatible pinned Python SDK/runtime dependencies after the capability probe; JavaScript Sandbox SDK release available at planning time is `3.6.1`.

**Spec:** `docs/superpowers/specs/2026-10-11-vercel-hobby-deployment-design.md`.

**Execution:** Native inline, as previously selected by the user. The latest request authorizes proceeding from the written design to this plan; review of this written plan remains required before product implementation or project provisioning.

## Global Constraints

- Project `outskill-group2-browser-studio`; account `testing-group1`, ID `team_vX4hl0qHhzt1aKFxd5wVJ7bU`; require plan `hobby`. Production branch is `demo_master`.
- No Pro upgrade, trial, payment method, paid resource, other hosting provider, or public laptop tunnel. Stop on unavailable free entitlement or exhausted quota.
- No Kane CLI. Retain native inline execution, Outskill styling, Group2 identity, local Docker isolation, and exactly one eligible repair/one retry.
- One active cloud generation/run job; ten-minute total budget. Controller sessions remain below the 45-minute Hobby maximum. Preserve existing narrower agent/attempt timeouts.
- Configure artifact admission cap `500 MiB`, database/key metadata cap `50 MiB`, and one deployment-configured daily regression window with explicit within-hour precision. No minute-accurate cloud guarantee.
- Credentials and API tokens remain server-side, never in Git, browser bundles, worker provider credentials, agent prompts, or logs. GitHub Secrets need an explicit Vercel runtime mapping.
- No cloud legacy-history import, local database/key upload, whole-repository runtime upload, or fabricated agent/browser evidence. Keep tests in Git; preserve local historical files when untracking them.
- No new general-purpose iterative discovery subsystem in this stage. Validate the current generic path against the approved external practice-login target; document dynamic-site/CAPTCHA/MFA/payment limitations.
- Work in the current feature branch and checkout to preserve the user's native preference. Read bundled Next.js version-specific docs before frontend changes.

## Review Focus

- Concurrent cold-start requests must resolve one controller/PID and preserve the same database rather than race into duplicate startup recovery (Task 2).
- Direct controller calls, malicious redirects/private-address targets, and agent-generated code must not bypass authentication or obtain management/provider secrets (Tasks 2–3).
- Expired SDK credentials, session interruption, repeated submit, and duplicate cron delivery must not replay browser side effects or report a fabricated pass (Task 4).
- Deletion scopes, symlinks, canonical baselines, and retained snapshots must not delete unrelated data or resurrect explicitly purged captures (Task 6).
- Large videos and expired media capabilities must play without Vercel's 4.5 MB proxy boundary, leaking API authority, or allowing file traversal (Task 5).

## File boundaries and shared interfaces

- `scripts/package_cloud_runtime.py`: allowlisted runtime archive/manifest, not deployment orchestration. `scripts/vercel_preflight.mjs`: account checks and disposable capability probe.
- `frontend/lib/server/cloudSettings.ts`: `CloudSettings` with project/account/environment, controller identity, runtime hash, limits, daily window, and server-only secret access.
- `frontend/lib/server/controller.ts`: `ensureController(settings: CloudSettings): Promise<ControllerHandle>`; `ControllerHandle = { name: string; origin: string; expiresAt: string; sourceRevision: string }`. Serializes trusted startup through an in-VM lock; no browser credentials returned.
- `backend/cloud_policy.py`: `CloudPolicy.from_env() -> CloudPolicy`; `backend/cloud_lifecycle.py`: controller readiness, job/session admission, startup recovery, and snapshot-safe drain.
- `backend/sandbox_runner.py`: `SandboxPlaywrightRunner`, preserving `PlaywrightRunner.execute_script(...) -> dict` and its `on_log`/`on_action` callbacks. `backend/sandbox_transport.py` owns SDK commands, file transfer, status checks, and worker cleanup.
- `backend/cloud_auth.py`: request/relay authentication and artifact capabilities. `backend/cloud_schedule.py`: `dispatch_daily(occurrence_id: str) -> dict`, separate from the local APScheduler timer.
- `backend/cleanup.py`: `preview_cleanup(scope: dict) -> dict` and `apply_cleanup(confirmation_token: str, purge: bool = False) -> dict`. `backend/api/cleanup.py` exposes authenticated preview/apply; existing deletion endpoints reuse this service.
- `frontend/lib/actionProgress.ts`: `reduceActions(events: ActivityEvent[]): ObservedAction[]`; one record per attempt/action ID. `ObservedAction` has `id: string`, `attempt: number`, `action: string`, `label: string`, `phase: "started" | "finished" | "failed"`, and optional `startedAt: string`, `finishedAt: string`, `durationMs: number`. Media access resolver and schedule/browser status copy remain separate concerns.
- `.github/workflows/deploy-vercel.yml`: verified deployment/secret mapping, not application execution. `docs/VERCEL_HOBBY.md`: exact operator commands, limits, URLs/access, cleanup, backup, and rollback.

---

### Task 1: Free-account preflight and safe runtime packaging

**Files:** Create `scripts/vercel_preflight.mjs`, `scripts/package_cloud_runtime.py`, `backend/tests/test_cloud_packaging.py`, `frontend/tests/cloud-preflight.test.ts`; modify `.gitignore` for generated runtime bundles.

**Interfaces:** Produces `RuntimeBundle = { archive_path, sha256, files }`, account-scoped probe receipt, and a pinned clean controller/worker runtime choice. Probe uses the approved account/project only, never application state.

- [ ] **Step 1: Write failing tests** `test_bundle_contains_required_backend_and_config_but_no_private_history`, `test_bundle_rejects_symlinks_outside_repository`, and `rejectsNonHobbyOrUnexpectedAccount`. Assert source/config/demo assets are present; `.env`, `.venv`, databases, keys, `artifacts/`, legacy captured JSON, tests, and documentation are absent; wrong account/plan performs no create call.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_cloud_packaging.py -q` and `npm --prefix frontend test -- --run tests/cloud-preflight.test.ts`.
- [ ] **Step 3: Implement** `package_runtime(repository_root: Path, output_dir: Path) -> dict` and `verifyFreeTarget(account: AccountSummary, expectedSlug: string): void`; parse metadata only and produce a deterministic archive/manifest from exact allowlisted files. Use a task-specific output directory, not the workspace root.
- [ ] **Step 4: Provision/probe only after this plan's approval.** Confirm CLI identity and Hobby status, create/link the exact approved project if absent, then verify clean Sandbox execution and persistent synthetic-file stop/resume. Verify SDK interfaces actually exist in the pinned installed SDK, snapshot retention controls work, and usage remains included. Record IDs and stop/delete only disposable probes. Entitlement/persistence failure stops the deployment—no paid fallback or claim of readiness.
- [ ] **Step 5: Verify GREEN**, inspect the archive manifest and synthetic persistence receipt, and commit only scripts/tests/ignore changes as `build: add free cloud preflight and runtime bundle`.

### Task 2: Authenticated persistent controller and gateway

**Files:** Create `frontend/lib/server/cloudSettings.ts`, `frontend/lib/server/controller.ts`, `backend/cloud_policy.py`, `backend/cloud_auth.py`, `backend/cloud_lifecycle.py`, `frontend/tests/cloud-controller.test.ts`, `backend/tests/test_cloud_controller.py`; modify `frontend/app/api/[...path]/route.ts`, `frontend/next.config.ts`, `backend/config.py`, `backend/server.py`, `backend/test_suite_manager.py`, `config/application.json`, and dependency/lockfiles.

**Interfaces:** Consumes Task 1's runtime bundle; produces `ensureController(...)`, `CloudPolicy.from_env()`, authenticated readiness and server-side gateway forwarding. Local profile preserves current routing and startup behavior.

- [ ] **Step 1: Write failing tests** `concurrentBootstrapStartsOneProcess`, `resumingPreservesDatabaseAndCredentialKey`, `test_cloud_management_requires_auth`, `test_cloud_has_no_legacy_import`, and `test_expired_sdk_credentials_fail_before_worker_creation`. Assert concurrent bootstrap returns the same controller, only one startup/recovery runs, wrong/missing auth returns `401`, synthetic target GETs are the only public routes, source revision updates leave state paths untouched, and missing cloud auth cannot start an unsecured backend.
- [ ] **Step 2: Verify RED** using the exact new frontend/backend test files with Vitest/Pytest.
- [ ] **Step 3: Implement** the shared controller/settings interfaces and `authenticate_cloud_request(request: Request, policy: CloudPolicy) -> None`. Use stable environment-scoped controller names, an in-VM startup lock, bounded health polling, explicit startup secret injection, and controlled source upgrades. Gateway overwrites trusted auth headers server-side, rejects unapproved targets, and returns an actionable temporary unavailable response on bootstrap failure.
- [ ] **Step 4: Implement cloud-specific lifecycle wiring**: database/key live outside source releases, disable cloud legacy import and local background timer, keep preview/production isolated, and do not replace an existing workspace on a failed migration/startup. Secret values and OIDC credentials never enter bundle manifests, URLs, or logs.
- [ ] **Step 5: Verify GREEN**, run existing configuration/proxy/vault tests for local compatibility, and commit as `feat: add protected persistent cloud controller`.

### Task 3: Isolated cloud inspection and Playwright execution

**Files:** Create `backend/sandbox_transport.py`, `backend/sandbox_runner.py`, `backend/tests/test_sandbox_runner.py`, `backend/tests/test_cloud_network.py`; modify `backend/runner.py`, `backend/page_controls.py`, `backend/n8n_client.py`, `backend/server.py`, and runtime packaging/dependencies where required.

**Interfaces:** Consumes `CloudPolicy` and trusted SDK startup credentials; produces the existing runner result/callback contract from ephemeral microVM workers. `validate_public_target(url: str, allowed_origins: set[str]) -> str` rejects disallowed navigation; a cloud inspection adapter returns the existing bounded value-free control summary.

- [ ] **Step 1: Write failing tests** `test_worker_has_only_approved_auth_and_run_environment`, `test_worker_does_not_inherit_controller_snapshot`, `test_nonzero_exit_is_failure`, `test_worker_stops_on_timeout_or_parse_error`, `test_private_ip_dns_redirect_and_metadata_are_blocked`, and `test_discovery_inspection_is_isolated`. Assert no provider/n8n/database/signing secrets in worker environment/files; no inherited controller filesystem; worker cleanup occurs on every outcome; hostile navigation never reaches the blocked destination.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_sandbox_runner.py backend/tests/test_cloud_network.py -q`.
- [ ] **Step 3: Implement** `SandboxPlaywrightRunner.execute_script` with the same arguments as the existing runner. Reuse validated script instrumentation and capture helpers, explicit bounded output paths, exit-code checking, redacted streaming, bounded artifact collection, and a clean `persistent=False` worker. No untrusted browser/script runs inside the trusted controller.
- [ ] **Step 4: Implement inspection/network routing** through the same isolated transport. Runtime setup/package installation occurs before restricted target execution. Enforce allowed public target/dependency origins at worker egress and validate DNS/redirects; reject controller management access even when the synthetic target shares its origin. Do not silently enable unrestricted egress or local unsafe execution.
- [ ] **Step 5: Verify GREEN**, including existing runner/failure-context/repair-preservation tests and one real cloud Chromium navigation/recording with synthetic data; commit as `feat: execute Playwright in isolated cloud workers`.

### Task 4: Session-safe jobs and the Hobby daily window

**Files:** Create `backend/cloud_schedule.py`, `backend/tests/test_cloud_jobs.py`, `backend/tests/test_cloud_schedule.py`, `frontend/app/api/cron/regression/route.ts`; modify `backend/cloud_lifecycle.py`, `backend/generation.py`, `backend/orchestrator.py`, `backend/scheduler.py`, `backend/api/schedules.py`, `backend/database.py`, `frontend/app/schedules/page.tsx`, `frontend/app/settings/page.tsx`, and tracked cloud settings.

**Interfaces:** Produces `dispatch_daily(occurrence_id: str) -> dict` and controller job admission. Mutating submit endpoints persist operations before accepting them; reads do not extend idle deadlines indefinitely.

- [ ] **Step 1: Write failing tests** `test_one_cloud_job_is_admitted`, `test_job_rejected_without_ten_minute_session_budget`, `test_interrupted_queued_generation_is_not_replayed_in_cloud`, `test_duplicate_submit_and_daily_occurrence_run_once`, and `test_daily_set_over_budget_is_rejected_before_any_execution`. Assert busy submissions return a clear conflict, interrupted operations become needs-attention/failed with an interruption reason, repeated requests do not invoke the browser twice, and assertion/business failures preserve the existing no-weakening policy.
- [ ] **Step 2: Verify RED** with the two new backend test files and schedule UI tests added to the existing frontend test layout.
- [ ] **Step 3: Implement** a ten-minute total job budget and controller drain/admission checks; reuse persisted idempotency and one active-job guard. Preserve local queued recovery separately; cloud recovery must not automatically execute abandoned browser effects. Stop completed workers promptly and idle controllers after a bounded grace period.
- [ ] **Step 4: Implement daily dispatch** with persisted occurrence claims, authenticated `CRON_SECRET`, one tracked daily UTC window, and no in-process cloud timer. Saved scripts run directly; discovery is not invoked on rerun/schedule. UI exposes the fixed window, within-hour precision, redeployment requirement, and independent on-demand control.
- [ ] **Step 5: Verify GREEN**, including local scheduler tests and forced controller stop/resume with an active synthetic job; commit as `feat: bound cloud jobs and daily regression`.

### Task 5: Private large media and a real local headed companion

**Files:** Create `backend/api/media.py`, `backend/tests/test_cloud_media.py`, `frontend/lib/artifactUrl.ts`, `frontend/tests/cloud-media.test.ts`; modify `backend/cloud_auth.py`, `backend/api/system.py`, `backend/api/__init__.py`, `backend/api/companions.py`, `frontend/components/runs/RunMedia.tsx`, `frontend/components/runs/RunVisual.tsx`, `frontend/app/settings/page.tsx`, `companion/browser_companion.py`, and companion tests as required.

**Interfaces:** `issue_artifact_capability(artifact_id: str, now: int) -> str` signs one artifact for 120 seconds; `resolveArtifactUrl(artifactId: string): Promise<string>` returns a fresh media URL. Companion profile contains only the current backend origin and scoped pairing/relay information, never controller/Vercel authority.

- [ ] **Step 1: Write failing tests** `test_signed_url_is_artifact_scoped_and_expires`, `test_media_denies_deleted_files_traversal_and_symlinks`, `test_large_video_range_response`, `refreshesMediaCapabilityAfterResume`, and `test_companion_disconnect_does_not_fallback_headlessly`. Assert capabilities cannot authorize an API action, expired URLs are rejected, unrelated paths cannot be read, and a synthetic video larger than 4.5 MB is served directly with valid range metadata.
- [ ] **Step 2: Verify RED** using new media tests and existing companion tests.
- [ ] **Step 3: Implement** signed, short-lived direct controller media URLs with containment checks, range responses, restrictive cache/referrer headers, and sanitized access logs. Local URLs retain existing behavior; cloud players refresh expired capabilities without proxying full videos through Functions.
- [ ] **Step 4: Implement session-bound Browser setup/profile refresh** and cloud relay authentication compatible with the existing outbound companion. Preserve explicit approval before opening local Chromium, never expose a public debugging port, and surface disconnect/expiry rather than implicitly switching browser mode.
- [ ] **Step 5: Verify GREEN** using media/companion tests and the existing local headed path; commit as `feat: secure cloud media and headed browser access`. The actual headed execution against the protected remote preview belongs to Task 8, after deployment exists.

### Task 6: Complete confirmed cleanup and a fresh deployment

**Files:** Create `backend/cleanup.py`, `backend/api/cleanup.py`, `backend/tests/test_cleanup.py`; modify `backend/api/runs.py`, `backend/api/journeys.py`, `backend/api/projects.py`, `backend/api/demo_lab.py`, `backend/api/operations.py`, `backend/api/__init__.py`, `backend/artifact_store.py`, `backend/cloud_lifecycle.py`, and repository/data wiring as needed.

**Interfaces:** `preview_cleanup(scope: dict) -> dict` returns exact counts/IDs and a 120-second confirmation token binding the scope/version; `apply_cleanup(confirmation_token: str, purge: bool = False) -> dict` rejects changed or active scope. Reuse these checks for single-resource DELETE APIs.

- [ ] **Step 1: Write failing tests** `test_cleanup_blocks_active_descendants`, `test_project_cleanup_removes_audit_operations_baselines_and_artifacts`, `test_run_cleanup_preserves_saved_script_and_baseline`, `test_changed_scope_invalidates_confirmation`, `test_cleanup_preserves_unrelated_scope`, and `test_purge_cannot_restore_captures_from_old_snapshot`. Cover scenarios, schedules, encrypted credentials, trash, canonical baseline paths, and hostile filesystem links.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_cleanup.py -q`.
- [ ] **Step 3: Implement** transactional metadata cleanup and root-safe recoverable artifact trash. Include exact scope manifests, stale confirmation rejection, active-operation `409`, explicit workspace-reset confirmation, and idempotent retry-safe filesystem reconciliation. Key replacement is permitted only when no retained encrypted credentials depend on it.
- [ ] **Step 4: Implement explicit purge/restore-point maintenance**: drain writes, publish a clean restorable state, then remove superseded restore points and scoped trash. Failed snapshot publication must not destroy the only good restore point or falsely claim permanent purge. Provide protected database/key export and restore verification.
- [ ] **Step 5: Verify GREEN** plus existing deletion/API tests. Review the exact historical Git manifest, untrack only captured history/artifacts while retaining local copies and intentionally published synthetic showcase docs; commit as `feat: add complete scoped cloud cleanup`.

### Task 7: Nonduplicative actual-action logs

**Files:** Create `frontend/lib/actionProgress.ts`, `frontend/tests/action-progress.test.ts`; modify `backend/action_events.py`, `backend/runner.py`, `backend/sandbox_runner.py`, `backend/orchestrator.py`, `backend/event_store.py`, `frontend/components/runs/LiveRunProgress.tsx`, `frontend/components/runs/RunLogs.tsx`, and relevant backend instrumentation tests.

**Interfaces:** Each observed action emits `action_id`, safe `label`, `action`, `phase`, attempt, timestamp, and elapsed duration; `reduceActions(events)` yields one stable row per `(attempt, action_id)`. Existing persisted events without IDs remain readable through a documented legacy fallback.

- [ ] **Step 1: Write failing tests** `test_expect_emits_one_outer_action`, `test_action_label_contains_no_fill_value`, `reducesStartedFinishedToOneRow`, `doesNotMergeDifferentAttempts`, and `reconnectDoesNotDuplicateActionRows`. Assert five actual actions produce five rows rather than ten phase rows; failed/started-only actions retain their truthful status.
- [ ] **Step 2: Verify RED** using the exact instrumentation and new action-progress test files.
- [ ] **Step 3: Implement** correlated action events without wrapping nested `expect` construction as another action. Generate safe labels from observed method/locator context, redact before persistence, and preserve the script's exception/return behavior.
- [ ] **Step 4: Implement** reducer-backed progression and a concise primary console with one meaningful lifecycle fact per occurrence. Planned steps remain separate; optional technical events stay redacted. Do not mark planned or missing actions complete.
- [ ] **Step 5: Verify GREEN** plus existing live-progress/browser UI tests, inspect a real execution stream, and commit as `feat: make browser action progress concise and truthful`.

### Task 8: Secret mapping, production deployment, and real evidence

**Files:** Create `.github/workflows/deploy-vercel.yml`, `frontend/vercel.json`, `frontend/.vercelignore`, `scripts/configure_vercel_secrets.mjs`, `docs/VERCEL_HOBBY.md`, and new deployment policy tests; modify root build/runtime bundle wiring, `README.md`, `docs/LOCAL_HEADED.md`, `docs/hackathon/README.md`, and architecture/showcase artifacts after verified deployment.

**Interfaces:** Consumes all earlier cloud interfaces. GitHub provides `N8N_BEARER_TOKEN` and `VERCEL_TOKEN`; generated application secrets exist only in private Vercel environments. Public deployment metadata records the approved account/project, source revision, runtime hash, and resulting URL without secret values.

- [ ] **Step 1: Write failing deployment-policy tests** asserting exact account/project/production branch, no paid-plan/provisioning command, one daily cron, isolated preview/production settings, server-only secret mapping, and no secret interpolation into command arguments/log output or public `NEXT_PUBLIC_*` values. Verify generated application secrets are reused rather than rotated on every deployment.
- [ ] **Step 2: Verify RED** with the new policy tests. Read current CLI help and official deployment docs before selecting flags; read installed Next.js docs for output tracing/root inclusion.
- [ ] **Step 3: Implement private secret setup/deployment workflow** restricted to trusted branch/manual dispatch, not untrusted pull requests. Map the two existing GitHub secrets explicitly; generate missing controller/signing, companion-admin, and cron secrets privately; retain them on repeat deploys. Keep project/team IDs and safe settings in configuration. Build once, protect preview/production, include the approved runtime bundle, and never upload the local `.env`.
- [ ] **Step 4: Run full fresh verification**: backend and companion Pytest suites, frontend Vitest, lint, production build, workflow validation, runtime-manifest inspection, and native Playwright UI coverage. Reconcile each failure and record current command results; earlier passing receipts do not prove the changed branch passes.
- [ ] **Step 5: Run the integration gate** using the required fresh whole-branch review for native execution. Preserve unrelated user work, integrate the verified branch into local `demo_master`, push, and create/attach a PR if the reviewed integration workflow calls for one. Do not rewrite shared history. Deploy a protected preview through the GitHub workflow and verify runtime/protection before production promotion.
- [ ] **Step 6: Verify real remote end to end**: fresh counts; n8n discovery; recorded synthetic register/login/cart/checkout; saved-script rerun without discovery; actual locator failure/repair/one retry; visual baseline/current/diff with actual configured visual-agent invocation; business failure without weakened checks; approved external practice-login; local headed companion; large-media playback; authorization/SSRF/containment checks; duplicate submit/cron; interruption/stop/resume; complete scoped cleanup/purge/backup restore. Retain sanitized agent IDs, run IDs, invocation evidence, and failures honestly. Daily trigger logic can be invoked explicitly for acceptance, but report the actual daily cron delivery separately until observed.
- [ ] **Step 7: Promote only a verified preview**, provide the actual production URL/share-access instructions, and confirm its health and browser journey again. Save remote evidence outside the app workspace, then remove only the confirmed validation scope and verify empty dashboard counts. Update the architecture to the deployed topology and hand off a labelled video under two minutes, exact deployment/local-headed/cleanup/rollback commands, free limits, and any unverified item.
- [ ] **Step 8: Commit/push verified deployment and evidence updates** as `deploy: publish verified Group2 Studio on Vercel Hobby`. Final handoff distinguishes implemented, locally verified, remotely verified, and remaining limitations; never claim a working deployment before its URL and run evidence exist.

## Self-review and execution handoff

Coverage: Tasks 1–3 implement isolation, hosting, runtime hygiene, authentication, and persistence; Task 4 owns job budgets/recovery/daily-window behavior; Task 5 owns large-media and headed sessions; Task 6 owns all scoped cleanup and restore-point safety; Task 7 owns meaningful logs; Task 8 owns private GitHub mapping, verification, integration, deployed evidence, and user steps. Generic-flow guarantees remain limited exactly as stated in the spec.

The five Review Focus conditions are pinned by named tests in their owning tasks. Shared signatures above are authoritative; preserve existing runner callback/result contracts rather than creating a second API. Free-capability failure stops at Task 1. Native execution is already selected; the remaining handoff is review and confirmation of this written plan.

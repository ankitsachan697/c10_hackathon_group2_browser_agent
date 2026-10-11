# Vercel Hobby deployment design

Date: 2026-10-11. Scope: a shareable, non-commercial Group2 hackathon demo using only Vercel's included Hobby resources and the existing n8n account. Conversational approach and destination approved; this written design awaits review. No remote deployment has been created or verified.

## Outcome and constraints

Deploy Outskill Browser Automation Studio to the approved `testing-group1` Hobby account as `outskill-group2-browser-studio`. A reviewer can supply an objective and target, configure optional credentials, verify and record, inspect actual actions and artifacts, and replay saved Playwright scripts. The deployed synthetic shop supports a reproducible registration/login/cart/checkout, locator repair, visual difference, and business-failure demonstration.

Do not upgrade to Pro, start a trial, add a payment method, provision paid resources, or introduce another hosting provider. Existing n8n/model consumption is separate from Vercel's free allowance; do not describe those model calls as free. If a required capability is unavailable on this Hobby account, stop and report it instead of silently changing the plan or exposing a laptop through a public tunnel.

Use native inline implementation, not Kane CLI. Preserve the Outskill theme, Group2 identity, existing local Docker execution, and the approved one-repair/one-retry policy. Tests remain in Git but are excluded from runtime packages. Do not remove unrelated files or user data.

This is a bounded-usage hackathon deployment, not an always-on service or a claim that arbitrary websites always automate successfully.

## Repository evidence and necessary changes

The current Next.js gateway forwards requests to a configured long-running FastAPI service. SQLite, credentials, artifacts, background operations, overlap guards, and the companion relay belong to that single backend process. Moving that process directly into independently scaled Vercel Functions would break those assumptions.

The current runner executes generated scripts in Docker locally. Cloud execution needs an isolated Sandbox adapter; disabling isolation is not acceptable. Discovery currently summarizes only the starting page. Planned steps are not proof that subsequent pages were inspected or actions executed.

Run deletion already blocks active runs and removes associated audit records. Journey/project deletion does not yet provide equivalent artifact and active-operation handling, and scenario/generation cleanup is incomplete. Older captured files remain tracked under `artifacts/`; legacy JSON history is automatically imported at startup. A fresh clone is therefore not sufficient to guarantee a fresh deployed workspace.

These hosting, cleanup, and action-log changes form this implementation stage. A new general-purpose, iterative browser-discovery agent is a separate stage: this deployment must expose the current discovery limitation honestly rather than disguise it as universal support.

## Selected architecture

Use three boundaries:

1. **Next.js on Vercel Hobby:** the existing Studio, authenticated API gateway, Sandbox lifecycle bootstrap, daily trigger, and deployment health/status. Vercel OIDC authenticates the server-side Sandbox SDK. Browser clients never receive Vercel or n8n credentials.
2. **One trusted persistent control Sandbox per deployment environment:** the existing Python/FastAPI services, one SQLite writer, credential vault, action/audit records, synthetic shop, visual comparison, and scoped companion relay. Its filesystem is snapshotted when stopped and restored on resume. Start the trusted backend on create and on resume; running processes do not survive a stop.
3. **Separate ephemeral execution Sandboxes:** Chromium inspection and execution of untrusted generated Playwright scripts. Each worker has a private filesystem and bounded lifetime. It receives the target, validated script, scoped browser credentials, and only its own output directory. It receives no database, credential-vault key, n8n token, Vercel credential, or controller filesystem.

Do not fork the trusted controller to create workers: forks can inherit environment and filesystem secrets. Workers originate from a clean, pinned browser runtime. Preserve the runner's log/action/artifact/result contract behind a configurable local-Docker/cloud-Sandbox adapter.

A Marketplace database, Sandbox Drive, Workflow subsystem, and Blob store are not required for this first deployment. In particular, the Sandbox pricing and SDK pages disagree about Drive availability; do not depend on Drives or a paid/private-beta entitlement. Persistent Sandbox snapshot support must be proven on the approved Hobby account before proceeding.

### Controller startup and coordination

Use a stable controller name scoped to project and environment, not a name per HTTP request or source revision. SDK bootstrap resolves that controller, resumes it, installs only the approved runtime bundle when necessary, and waits for authenticated readiness. An in-Sandbox lock ensures that concurrent bootstrap requests start only one FastAPI process and do not run startup recovery twice.

Database and key paths are outside versioned source directories. A source update preserves data, takes a schema backup, applies compatible migrations, and switches source only after readiness. Deployment failure must not initialize a replacement database over an existing one. Preview and production environments use different controller names, data, and secrets.

Trusted SDK credentials are supplied explicitly to the controller at process startup, not assumed to appear automatically inside an arbitrary VM. They are not written into the runtime bundle or passed to workers. Check their validity before worker creation; expired credentials produce a visible infrastructure error and require a fresh authenticated bootstrap.

### Jobs and session limits

Create/generate/run requests persist an idempotent operation and return promptly. Work continues inside the controller session, not in an unawaited Vercel Function task. Polling reads persisted status and actual event sequence numbers. Refreshing the page never starts another execution.

One generation/run job is active at a time in this demo deployment. Additional submissions return a clear busy response, not a silently growing queue. Each submitted job has a configurable ten-minute total budget, including discovery, execution, repair, and visual comparison. Keep existing per-agent and per-attempt limits within that budget.

Controller sessions are explicitly bounded below Hobby's 45-minute maximum. Before accepting work, verify enough session time remains for the entire job; otherwise drain and resume the controller before submission. Reads and dashboard polling do not indefinitely extend an idle session. Stop idle sessions and completed ephemeral workers promptly.

An unexpected stop marks incomplete work `NEEDS_ATTENTION` on recovery. Never automatically replay browser side effects after infrastructure interruption. A saved-script failure gets at most the existing single eligible repair attempt and single retry, with both attempts retained; business/assertion failures must not be converted into passes by removing checks.

### Network and access control

Protect preview and production Studio access with Hobby-compatible Vercel Authentication/share links. The publicly routable controller has independent server-side authentication: hiding it behind the UI alone is insufficient. All management, execution, mutation, logs, credentials, and arbitrary artifact routes require a controller secret or a narrower, expiring capability. Fail closed when cloud authentication is missing.

The only public target routes are the synthetic demo-shop HTML and its two static assets. They expose scenario switches and synthetic content only, never stored scripts, submitted secrets, run data, or mutation endpoints. Generated workers reach this target using the controller's public HTTPS origin, not the protection-gated Studio origin. Studio-generated demo objectives must use that configured target origin.

Worker egress allows the approved public target and explicitly configured public dependency origins. Block private addresses, cloud metadata, unapproved redirects, and access to controller management routes. DNS resolution and redirects must not bypass the policy. External sites needing additional asset/login origins show an actionable configuration error rather than enabling unrestricted network access.

Treat page content as untrusted evidence, not instructions. AST validation remains a defense in depth; it is not a replacement for worker isolation and network restrictions.

## Persistence, media, and a fresh workspace

The controller's persistent snapshot contains SQLite and its automatically generated credential key together, plus bounded private artifact files. Use the minimum required snapshot retention, with the current restore point retained without the default inactivity expiration. Prune older restore points after successful replacement. This is session-snapshot persistence, not a continuously replicated database: unexpected termination can interrupt work and requires recovery checks.

Set configurable application caps of 500 MiB for live artifacts and 50 MiB for database/key metadata; enforce admission checks before recording. These caps are additional safeguards, not replacements for Vercel account quotas. Keep runtime images and retained snapshots within the included snapshot storage. Never auto-delete baseline evidence simply to admit another run; report that cleanup is required.

Large videos bypass Vercel Function proxy payload limits. The authenticated Studio requests an artifact-scoped HTTPS URL signed by the controller, valid for a short interval. The media endpoint validates the signature, expiry, artifact identifier, and containment before streaming, supports range requests, sends restrictive cache/referrer headers, and refuses traversal. The URL grants access only to that artifact, not the API or browser relay. Playback refresh obtains a new URL after a session resume.

Mask passwords in the form and redact credentials, card details, tokens, and other configured sensitive values from agent payloads, logs, DOM captures, and script displays. Do not claim that arbitrary page/video pixels can be perfectly redacted. Capture only approved synthetic data in showcase recordings; make evidence privacy limits visible before a reviewer enters real sensitive data.

First production startup creates a new, empty domain database. Disable legacy JSON import in the cloud profile, and never upload the local database, private key, `.env`, captures, or recorded run history. Keep the static synthetic shop available without seeding journeys or runs. After remote validation, use the cleanup API to remove only the validation workspace and confirm the public dashboard is fresh.

Provide an authenticated export procedure for operator backups of database and key together. Document that deleting the persistent controller/its final snapshot without a backup destroys its workspace. Never delete those resources as part of ordinary source deployment.

## Complete, scoped cleanup

Centralize deletion behavior so individual run, journey, and project deletion share active-operation checks and artifact containment rules. Reject deletion with `409` when the scope contains active work; do not cancel or kill executions implicitly.

Provide authenticated cleanup preview and apply endpoints. A preview identifies exact project/journey/run/scenario/generation-operation IDs, dependent audit records, canonical baselines, and artifact paths. Applying requires the returned confirmation token and refuses changed or expanded scope. A workspace-wide reset requires an explicit reset scope and separate confirmation.

Delete dependent audit records and generation references consistently. Journey/project cleanup includes their canonical baselines; deleting a run alone preserves the journey's baseline and saved script. Scenario deletion is refused while referenced by an active operation or retained journey unless that journey is explicitly included in the confirmed scope.

Use recoverable artifact trash for normal deletion, with documented retention and explicit purge. A purge removes scoped artifacts, trash, credential references, and superseded restore points that could restore purged captures; publish a clean restore point before retiring the old ones. State the distinction between removed from the UI, recoverable deletion, and permanent purge.

An empty-workspace verification checks projects, journeys, runs, operations, scenarios, activity, invocations, baselines, and live artifacts. Keep deployment authentication/configuration unless explicitly requested otherwise. Private keys are replaced only when no retained encrypted credentials depend on them.

For repository hygiene, untrack only the reviewed historical-capture manifest and legacy captured-history files, preserving local copies. Retain intentionally published synthetic showcase media and documentation under `docs/hackathon/`, as well as tests and fixtures. Runtime packaging uses an explicit allowlist of application source, required config, static assets, lockfiles, and dependencies; no whole-repository or `.env` upload.

## Meaningful action logs and generic behavior

Give each observed action a correlation ID within its attempt. Starting, finished, and failed events update one action row, rather than rendering three separate actions. Include a safe human-readable action/locator label and duration; never include filled values. Suppress duplicate nested expectation instrumentation and duplicate lifecycle narration.

Keep discovery's proposed steps separate from actual browser actions. The primary live console reports meaningful lifecycle facts once; an optional technical view can retain raw redacted events. Reconnects merge by persisted sequence/action ID. Missing observations remain unknown, not automatically marked done.

Do not hardcode demo-site locators, success text, credentials, or domains into general generation/execution paths. A new target gets a new discovery operation using its observed controls; normal reruns and daily executions use its saved script directly, without calling discovery again. Repair and visual agents are invoked only for their configured purposes, and their invocation records are visible.

Validate the existing generic path against the independently hosted, already approved practice-login site as well as the synthetic shop. Registration/checkout support elsewhere depends on actual accessible controls and assertions. Dynamic multi-page discovery, CAPTCHA, MFA, anti-bot challenges, real payments, and arbitrary cross-origin authentication are not promised by this stage. Unsupported flows fail clearly without fabricated evidence. A separate bounded state-aware discovery design is required before claiming those flows work generically.

## Headless, headed, and daily execution

Remote default: Chromium runs headlessly in an isolated cloud worker, with logs, screenshots, and video displayed in Studio.

Local headed option: the reviewer installs Playwright Chromium and the existing local companion, pairs it through authenticated Browser setup, and opens an outbound TLS connection to the active controller's scoped relay. No public local debugging port. The cloud UI must not imply a Linux headless VM is a visible desktop browser.

Pairing and the relay are session-bound. Disconnects, controller expiration, and unavailable local browsers fail visibly; Browser setup supplies a fresh connection profile after resume. A headed execution requires an online companion for its entire run and falls back to headless only with the reviewer's explicit choice. The deployment runbook includes real macOS/Linux/Windows setup commands appropriate to the supported companion runtime.

For this Hobby release, cloud automatic regression uses **one deployment-configured daily window**, not arbitrary minute-accurate schedules. The authenticated cron trigger bootstraps the controller and runs the enabled saved-script set once for that daily occurrence. Persist occurrence IDs to prevent duplicate cron deliveries and disable the in-process timer in the cloud profile. Enforce the total job budget; a set that cannot fit is rejected rather than partially presented as complete.

The UI labels the selected window and explains Hobby's within-hour timing. Changing the cloud window updates tracked deployment configuration and requires redeployment. The local continuously running scheduler retains its existing time/timezone behavior. On-demand execution remains available independently of the daily window. Do not use a paid trial or an undocumented scheduling workaround to promise exact-minute cloud execution.

## Free-account limits and deployment sequence

Official documentation checked on 2026-10-11 lists Hobby Sandbox allowances of 5 active CPU hours/month, 420 GB-memory hours/month, 5,000 creations/month, 20 GB transfer/month, 15 GB snapshot storage, ten concurrent Sandboxes, and a 45-minute maximum session. Included quotas are shared with other account usage. Hitting them pauses availability; it does not justify upgrading or promising uninterrupted access. Vercel Functions on Hobby have a five-minute duration limit and a 4.5 MB request/response payload limit.

Deployment order after the written spec and implementation plan are approved:

1. Recheck signed-in identity, `testing-group1` Hobby status, available quota, and exact project name. Create/link only the approved project; refuse similarly named projects in other scopes.
2. Run a minimal isolated Sandbox persistence/stop/resume probe with synthetic data. Confirm the account can use the required free capabilities, and remove only disposable probe resources. Stop on entitlement or quota failure.
3. Implement and verify the gateway, controller lifecycle, worker adapter, cloud authentication, runtime allowlist, cleanup, and action-log contracts. Preserve local execution through the same interfaces.
4. Set Node/runtime versions, repository/root build settings, safe JSON configuration, and secrets through server-side environment controls. Deploy a preview; verify protection and health before publishing production.
5. Run real remote Chromium/n8n validation and save sanitized receipts. Confirm persistence across stop/resume and that no user action is replayed by recovery.
6. Push the verified commits, integrate into `demo_master` using the approved Git workflow, and provide the verified production URL, share-access instructions, daily-window limitations, local-headed steps, cleanup commands, and rollback procedure.
7. After evidence is saved outside the application workspace, delete the remote validation scope through the API and verify fresh dashboard counts. Keep the intentionally published synthetic handoff video and architecture documentation.

Secrets include the existing n8n bearer token, controller authentication/signing material, companion administration credential, and cron secret. Non-secret agent IDs, endpoints, feature flags, limits, branding, and schedule window remain in tracked configuration. GitHub Secrets do not automatically become Vercel runtime environment variables: an explicit deployment mapping or private Vercel environment setup is required. Do not reuse a token exposed in chat as a long-term deployment credential; request a rotated value through a private runtime secret channel.

## Acceptance evidence

Deployment is complete only after the following are verified on the actual production origin:

- Protected Studio and authenticated controller cannot be bypassed by calling public management/API/artifact URLs directly; expired capabilities and path traversal are rejected.
- Initially zero projects/journeys/runs/operations/scenarios and no historical imports or private files in the runtime bundle; dashboard numbers match persisted outcomes after creation and deletion.
- Real n8n discovery invocation creates a generic saved Playwright script, and the first real Chromium execution has observed actions, readable nonduplicative logs, screenshot evidence, and playable video.
- Synthetic registration/login/cart/checkout passes; a target locator change produces a real failure, one real repair invocation, one retry, preserved assertions, and `PASSED_AFTER_REPAIR` only after verified success.
- A visual-only change creates baseline/current/diff evidence and the configured visual-agent invocation while retaining separate functional and visual outcomes. A business/assertion failure stays `NEEDS_ATTENTION` without weakened assertions.
- The approved external practice-login journey succeeds with credentials supplied through the UI, not embedded in agent prompts/scripts. Saved-script rerun invokes no discovery agent.
- Browser setup and one real paired local headed execution work against the deployed controller; disconnect behavior is visible and safe.
- Concurrent starts, page refresh, retries of submit/cron delivery, controller stop/resume, and interrupted jobs do not create duplicate actions or unwanted browser replays.
- Scoped deletion covers all captured record/artifact classes, blocks active work, preserves unrelated scopes, and can leave the remote workspace fresh. Explicit purge does not restore deleted data from a superseded snapshot.
- The shareable video remains under two minutes and labels shortened waits; the architecture/runbook reflect the deployed topology rather than the old local-only diagram. Report any unverified acceptance item explicitly, never as passed.

## Primary references and documented uncertainty

- [Vercel Hobby](https://vercel.com/docs/plans/hobby): non-commercial use, included limits, and deployment protection.
- [Sandbox pricing and quotas](https://vercel.com/docs/vercel-sandbox/pricing): Hobby allowance and pause behavior; pricing-page Drive rows are not proof of account entitlement.
- [Sandbox SDK reference](https://vercel.com/docs/vercel-sandbox/sdk-reference): persistent lifecycle, create/resume hooks, clean workers, snapshots, and the conflicting private-beta Drive restriction.
- [Cron usage and pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing): Hobby daily frequency and within-hour timing.
- [Function limits](https://vercel.com/docs/functions/limitations): function duration and payload boundaries.

Public documentation describes the proposed capabilities, but only the approved account probe establishes availability. No deployment URL, entitlement, account quota, remote headed run, or remote end-to-end success is claimed by this design document.

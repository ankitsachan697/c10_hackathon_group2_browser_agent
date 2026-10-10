# Live Agent Journey and Local Headed Execution

**Date:** 2026-10-11  
**Status:** Proposed for user review  
**Supersedes:** The creation, visual-monitor, and live-log portions of `2026-10-10-browser-automation-studio-design.md`. Saved-script execution and the one-retry policy remain in force.

## Outcome

A user enters a target URL, objective, optional credentials, and execution mode in one aligned journey form. Creating the journey invokes the configured n8n discovery/generation agent, saves the returned Playwright script, and immediately starts its first execution. The UI shows genuine generation milestones and redacted Playwright actions as they occur. On an eligible failure, the configured n8n diagnosis/repair agent returns a root cause and repaired script; the runner performs exactly one verification retry. On a completed attempt with suitable screenshots, a deterministic visual comparison runs, and the configured n8n visual agent summarizes the bounded comparison evidence. The first screenshot becomes a baseline only through a visible baseline policy; subsequent runs compare against it.

Normal on-demand, scheduled, project, saved-case, and rerun triggers continue to execute the saved script directly. They never regenerate it. They may still invoke repair after an eligible failure and visual review after execution.

## Current-State Findings Driving This Design

- The local `.env` disables n8n generation and repair, and `N8N_BEARER_TOKEN` is unavailable to the backend. Agent IDs in tracked JSON alone do not authenticate or invoke n8n.
- Generation currently accepts a request synchronously, silently falls back to a local synthesizer, saves a script, and does not run it. The response does not identify the actual source to the UI.
- The runner has an optional `headed` parameter and log callback, but orchestration does not pass either. The run page renders an empty log list.
- Repair is called only for deterministically eligible failures. The visual n8n agent is configured by ID but inactive at runtime; the Visual tab receives no run evidence.
- A hosted backend cannot access an arbitrary browser on a user's laptop. Its CDP endpoint requires a reachable, protected browser service or tunnel.

The private n8n agent definitions could not be inspected from this session. The application must verify their invocation contracts through authenticated integration tests before declaring the remote workflow operational.

## Chosen Architecture

Use an asynchronous, persisted run/event lifecycle rather than holding the create request open through browser execution. This preserves responsiveness and allows live UI updates. A local companion is the preferred headed-browser path for a hosted backend because it makes an outbound authenticated connection and does not expose a local debugging port. Existing private CDP remains an advanced deployment option. A synchronous create-and-run request is simpler but cannot reliably stream progress or survive page navigation; raw public CDP is rejected for security reasons.

### Generation and First Run

1. UI submits the single form once. The backend validates project, URL, objective, credential pair, and execution mode.
2. Backend creates a generation operation with a stable ID and emits `generation.started`.
3. n8n discovery agent `QEzE1lGs9WbTU82H` receives URL, objective, and `has_auth` only. Credentials are never sent. The adapter records request ID, agent ID, timing, outcome, and returned discovered steps; it does not claim to show internal n8n actions that n8n did not publish.
4. A valid generated script is policy-checked and saved as version 1. If n8n is disabled, missing authentication, times out, or returns invalid output, creation visibly fails with a configuration/agent error. A local synthesizer is available only through an explicit user-selected offline mode and is labelled as local output.
5. The first run is queued automatically and uses that saved version. The create command returns an operation ID promptly. The operation feed supplies journey and run IDs once generation succeeds, then the UI transitions to the live run view. For a hosted headed run, execution waits for the paired companion's explicit script approval.
6. Refresh or reconnect reads persisted state and events without duplicating generation or execution.

### Execution, Repair, and Visual Review

- The runner emits structured, ordered events for lifecycle changes and browser actions (`navigate`, `locate`, `click`, `fill`, `submit`, assertion, screenshot, close). Events include action type, safe target/locator, start/end, outcome, and duration, but never input values, passwords, tokens, or card data. Plain script stdout/stderr is redacted separately. If a generated script uses unsupported constructs, the UI reports only the actions observable through instrumentation; it does not invent events.
- Screenshots, video, and trace evidence are attached to the run. The UI distinguishes the live event stream from retrospective evidence. A user can switch tabs while execution continues.
- Deterministic failure classification runs first. Only eligible failures invoke repair agent `p3Sh9BmTzLMC0f8A` with a bounded, redacted packet. Root cause and proposed change remain visible alongside the original failed attempt. Exactly one repaired-script retry is allowed; a second failure becomes `NEEDS_ATTENTION`.
- Visual comparison uses local image analysis to produce counts, threshold, and artifact references. The first successful run with a usable final screenshot automatically establishes a clearly labelled baseline; an unsuccessful first run leaves `BASELINE_NEEDED`. Later baselines are never silently replaced after a difference. Visual agent `bS5GQjs2LrNHrJZH` receives only bounded metrics and safe artifact descriptions, not raw credentials, full DOM, or video. It summarizes a first-run baseline or subsequent difference; its opinion never silently changes a functional pass to fail. Visual review has an explicit state: `BASELINE_NEEDED`, `BASELINE_CREATED`, `MATCH`, `DIFFERENCE`, `UNAVAILABLE`, or `ERROR`.
- Agent invocations and their outcomes appear as distinct events (`discovery`, `repair`, `visual`). If an agent is not called, the UI explains why (for example, saved-script run passed or failure was ineligible).

### Headless, Headed, and Hosted Browser Location

- The one-page form offers `Headless` (default) and `Watch in browser` for the first run. Run-now actions may override the mode for that run. Daily schedules default to headless, independent of the last interactive choice.
- A backend on the presenter's machine may open local Chromium headed. A hosted backend uses a paired local browser companion for `Watch in browser`; the companion launches visible Chromium on that computer and relays its CDP connection outbound over an authenticated channel. The saved script and credentials remain in the backend's isolated runner; the companion never executes generated Python. The UI shows companion availability and refuses headed mode when no compatible companion is online.
- Pairing uses a short-lived, single-use code exchanged for a scoped credential. The companion verifies the server certificate, declares its capabilities, heartbeats, and accepts only sessions explicitly routed to its device. The user approves opening a local browser for the chosen run. No public Chrome debug port is opened.
- The existing configured private CDP endpoint remains usable for a managed browser or a pre-established private tunnel; merely choosing headed mode does not make a remote browser appear on a laptop.
- Because generated Python is sensitive, it stays in the existing isolated backend runner. The companion receives CDP traffic for the approved browser session, not code or credential values through a separate job API. Headed execution must not silently fall back to unsandboxed host Python.

## User Interface

The three-step wizard becomes one responsive form with sections for project, journey/target/objective, optional credentials, and an execution choice. Project creation remains inline via the existing dialog. Labels and controls align to a common grid; the password reveal control shares the input height and focus treatment. A compact pre-submit summary states `Generate script and run once` and names the selected browser location.

After submit, one run page shows a clear sequence: discovery, script saved, browser connected, actions, result, repair (when applicable), and visual review. A live activity panel defaults open, auto-scrolls unless the user scrolls away, supports filtering by source, and masks secrets. Agent activity is labelled with the actual source and agent ID, never inferred from a local fallback. The script, video, screenshots, failed attempt, repair diff, and visual comparison remain accessible without navigating away.

## Data and API Contracts

- Persist generation operations, run events, agent invocations, browser mode, browser target/companion ID, and visual review outcome with timestamps and stable IDs. Add migrations compatible with existing SQLite data.
- Add a start-generation command that is idempotent under a request key and returns promptly. Existing `POST /api/journeys/generate` may remain as a compatibility adapter until the UI migrates.
- Add a bounded event feed for a run and generation operation, using SSE with sequence IDs and reconnect support or an equivalent persisted polling fallback. Events are redacted before persistence and transmission.
- Extend run-start APIs with a per-run mode and optional companion target. Schedules retain headless defaults. Existing saved-script semantics remain unchanged.
- Add companion pairing, heartbeat, job claim, event upload, and completion endpoints with scoped authorization and explicit timeout/revocation behavior.
- Treat n8n failure as a visible error, not a successful `script ready` state. Record source, agent ID, duration, request correlation, and token usage only when the provider actually returns those fields.

## Error Handling and Security

- Validate and bound generated scripts before save and before execution. Do not print requests, tokens, credentials, or full prompts in events or logs.
- Do not disclose `N8N_BEARER_TOKEN` through public configuration, health payloads, browser requests, or companion messages. GitHub Secrets configure CI only; a running backend needs its own runtime secret. Safe IDs and flags remain in tracked JSON.
- A missing token or disabled agent yields actionable `AGENT_NOT_CONFIGURED`; invalid output yields `AGENT_RESPONSE_INVALID`; network failure yields `AGENT_UNAVAILABLE`. No silent n8n-to-local substitution.
- If the local companion disconnects before a job starts, keep the run queued for a bounded period and then mark it `NEEDS_ATTENTION`; if it disconnects mid-run, preserve received events and mark execution incomplete. Never silently execute the job on the server instead.
- Never guarantee that all visual secrets are masked: text redaction and field blur cover common patterns, but screenshots/video require review before sharing.
- Preserve original attempt, diagnosis, patched script, retry, and visual outcomes. Visual-agent failure does not erase the functional run result.

## Verification and Acceptance

1. With n8n enabled and authenticated, create calls the discovery agent exactly once, saves its valid script, queues the first run, and streams real events. A reload resumes the same operation.
2. With n8n disabled/missing token, creation shows a clear error; offline synthesis occurs only when explicitly selected and is labelled.
3. A passing saved-script run makes no discovery or repair call. An eligible failure calls repair once and retries once; an ineligible failure does not call repair.
4. Visual comparison runs after usable evidence; the visual agent is called with bounded data when enabled. First-run baseline and subsequent difference states are distinguishable.
5. Headless and headed modes reach the runner correctly. A hosted headed request requires a paired local companion and never exposes public CDP or falls back to an invisible server browser.
6. Live events identify agent versus Playwright sources, remain ordered and redacted, and render in the run UI. Input values cannot appear in events, stdout/stderr, persisted evidence text, or repair prompts.
7. Form alignment, responsive layout, keyboard access, focus order, and password masking are covered by component and browser checks.
8. Backend unit/integration tests, frontend tests, lint, build, and a controlled end-to-end demo pass before delivery.

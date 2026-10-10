# Browser Automation Studio Redesign

**Date:** 2026-10-10
**Status:** Approved design draft

## Purpose

Transform the current self-healing browser automation prototype into a polished, reusable hackathon product for QA teams. The product must create and maintain browser journeys, execute saved Playwright scripts on demand or on a daily schedule, retain useful evidence, attempt one eligible automatic repair, and clearly request human attention when that retry still fails.

The interface will use Outskill branding and visual patterns inspired by `xray_lens`, without using “enterprise” as product copy. Configuration, URLs, schedules, credentials, thresholds, branding, retry policy, and service endpoints must not be hardcoded into product behavior.

## Product Principles

1. Deterministic execution is the default. Agents are used only where reasoning adds value.
2. A run never silently rewrites history. Original failures, repairs, retries, and final outcomes remain visible.
3. The same orchestration service handles every operational trigger.
4. Destructive actions are explicit and recoverable where artifacts are involved.
5. A generic domain model supports authentication, checkout, data extraction, form filling, smoke tests, regression tests, and other browser journeys without use-case-specific code.
6. Routine passing runs consume no LLM tokens.

## Architecture

### Application shell

The Next.js application becomes a multi-view control center with persistent navigation:

- **Overview:** pass rate, recent runs, runs needing attention, repair activity, service health, and next scheduled execution.
- **Projects:** projects and their journeys with search, filters, run, edit, and delete actions.
- **Runs:** filterable execution history with inspect, rerun, delete, artifacts, trigger source, and outcome.
- **Schedules:** daily schedules with timezone, enabled state, next run, last run, and Run now.
- **Settings:** environments, browser defaults, thresholds, feature flags, and connection health.
- **Run detail:** timeline plus Evidence, Script, Repair, Logs, and Visual comparison views.

The existing 877-line dashboard will be decomposed into focused route views, reusable UI primitives, typed API access, and feature-specific components.

### Backend ownership

FastAPI is the authority for projects, journeys, schedules, runs, retry policy, and artifact metadata. SQLite replaces JSON files as the durable source of truth. Existing cases and run history are imported once so current work is preserved.

Artifacts remain filesystem-backed but are addressed through stable record identifiers. Deleted artifacts are moved into a recoverable trash area before later retention cleanup.

An application-owned scheduler persists daily schedules, supports IANA timezones, calculates the next execution time, restores jobs after restart, and prevents overlapping runs for the same scope.

### n8n responsibility

n8n remains a focused intelligence layer:

- Flow discovery and script generation are used only when a journey is created or a user explicitly regenerates its script.
- Error diagnosis and adaptive repair are invoked only after a saved script fails and deterministic classification marks the failure eligible for healing.
- Visual comparison remains local and deterministic.
- n8n unavailability does not prevent direct execution of saved scripts.

## Execution and Healing Model

Scheduled, on-demand, saved-case, project, and historical rerun triggers directly execute saved Playwright scripts. They do not invoke flow discovery or script generation.

The state machine is:

```text
Queued -> Running -> Passed
Queued -> Running -> Failed -> Diagnosing -> Repairing -> Retrying -> Passed after repair
Queued -> Running -> Failed -> Diagnosing -> Repairing -> Retrying -> Needs attention
```

Rules:

- Exactly one automatic repair and verification retry is allowed.
- Infrastructure, invalid credentials, unsupported assertions, and explicitly non-healable categories do not trigger blind repair.
- “Run now” always uses the saved script.
- A historical rerun uses the current saved journey script by default. “Run this version” uses the immutable script snapshot stored with that historical run.
- Project execution queues every active journey in the project using each journey's saved script.
- A healed pass retains its original failed attempt, diagnosis, patch, and retry evidence.
- After the repaired retry fails, the run becomes `NEEDS_ATTENTION` and offers inspect, edit, retry, approve repair, and archive actions.

## Token and Context Controls

- Passing saved-script runs make no LLM call.
- A deterministic classifier runs before diagnosis.
- Repair receives a compact failure packet containing the error category, final relevant traceback lines, failed action, locator evidence, bounded DOM/accessibility excerpt, and artifact references.
- Full logs, entire DOM documents, videos, and unrelated screenshots are excluded from prompts.
- Agent responses use strict JSON schemas.
- Repair should return a bounded patch plus explanation where possible rather than regenerate an unrelated script.
- Prompts use concise invariant rules and structured fields rather than repeating narrative context.
- Model, token ceiling, timeouts, and agent feature flags are configuration-driven.
- Run records retain agent invocation and token metadata when the provider exposes it.

## Domain Model

### Project

- ID, name, description, environment reference, tags, timestamps, archived state.

### Journey

- Project reference, name, objective, target URL, saved Playwright script, script version, active state, browser configuration, visual threshold, baseline state, and latest run summary.

### Schedule

- Journey or project scope, daily local time, IANA timezone, enabled state, overlap policy, next run, last run, and timestamps.

The initial implementation supports daily schedules. The model must allow future recurrence types without changing journey or run contracts.

### Run

- Journey/project reference, immutable script snapshot and version, trigger source, schedule reference, state, attempt count, timing, diagnosis, repair patch, final decision, visual outcome, and timestamps.

### Environment

- Name, base URL, non-secret variables, and runtime credential references. Plaintext secrets are never persisted in journey or run records.

### Artifact

- Run reference, artifact kind, storage path, media type, size, checksum where available, and deletion state.

## Lifecycle and Deletion

- Projects, journeys, schedules, and runs expose delete actions through contextual menus.
- Deleting a project requires confirmation that lists affected journey, schedule, run, and artifact counts.
- Project deletion cascades through related database records in one transaction.
- Associated artifacts are moved to recoverable trash.
- Individual run deletion removes its database record and moves its artifacts to trash.
- Project, journey, schedule, and run-history surfaces expose Run now where meaningful.
- Destructive operations return clear success or failure feedback and never rely on icon-only affordances.

## API Boundaries

Resource-oriented endpoints cover:

- `/api/projects`
- `/api/journeys`
- `/api/schedules`
- `/api/runs`
- `/api/environments`
- `/api/health`
- `/api/config/public`

Command endpoints delegate to the same orchestration service:

- Run a project or journey now.
- Rerun a historical execution with the current saved script.
- Run the historical script snapshot.
- Create or explicitly regenerate a journey script.
- Retry a run after manual edits.

API models use stable IDs, enumerated states, validation errors, and consistent response envelopes. Compatibility routes may temporarily adapt existing UI calls during migration.

## UI and Visual System

The visual system borrows the strongest patterns from `xray_lens`: a compact dark navigation shell, layered surfaces, restrained blue/indigo accents, clear status colors, readable density, and focused detail panels.

- The Outskill full logo appears in the expanded navigation; the compact mark appears when collapsed.
- Product copy uses “Browser Automation Studio” and operational language.
- The top bar reports backend, runner, scheduler, and n8n health.
- A primary New journey action opens a guided creation flow.
- Tables support search, filters, sorting, pagination, bulk selection, and meaningful empty/loading/error states.
- Context menus reduce button clutter.
- Destructive actions use accessible confirmation dialogs.
- Toasts report run starts, schedule changes, recoverable deletion, and failures.
- Run status is communicated by label, icon, and color.
- Run details show the execution timeline and separate evidence types into tabs.
- Repairs appear as a code diff alongside diagnosis and retry result.
- Schedule controls use local time, timezone, scope, enabled state, and overlap behavior in plain language.
- The interface supports laptop and presentation-screen layouts.
- Focus visibility, semantic labels, contrast, keyboard interaction, and reduced motion are required.

## Configuration and Security

- API base URL, paths, branding, retry count, timeouts, thresholds, scheduler behavior, retention, and feature flags come from environment-backed settings with safe defaults.
- Real credentials and production endpoints are not seed values in UI source code.
- Demo fixtures are isolated from product defaults.
- Credentials are referenced by keys and injected only into the runner process.
- Logs and persisted failure packets are redacted before storage or transmission.
- Artifact paths are resolved beneath configured roots and are not accepted as unrestricted filesystem paths.
- The pasted n8n bearer credential must not be committed and should be rotated after configuration.

## Error Handling

- API failures use structured codes and human-readable messages.
- Scheduler startup reconciles missed/next runs without duplicating execution.
- A run rejected because an identical scope is active records or reports a clear overlap decision.
- n8n outage leaves the failed run eligible for manual intervention rather than hiding the failure.
- Partial artifact failure does not overwrite the underlying execution result.
- Database mutations affecting multiple resources are transactional.

## Validation Strategy

- Unit tests cover repositories, scheduling calculations, overlap prevention, state transitions, deletion, redaction, failure-packet compaction, and repair eligibility.
- API integration tests cover CRUD, Run now, historical rerun choices, one-retry enforcement, cascade deletion, artifact trash behavior, and restart-safe schedules.
- Frontend tests cover navigation, forms, confirmation dialogs, status rendering, filters, action menus, and error/empty/loading states.
- Production type-check, lint, and build must pass.
- Accessibility checks cover keyboard navigation, names, focus, contrast, reduced motion, and dialog behavior.
- Browser validation covers journey creation, direct saved-script execution, daily schedule creation, manual Run now, eligible repair and pass, retry failure to Needs attention, historical rerun, and project/run deletion.

## Acceptance Criteria

1. No scheduled, on-demand, saved-case, project, or rerun path invokes discovery/script generation.
2. A passing saved-script execution uses no LLM.
3. An eligible failure receives at most one automatic repair and retry.
4. A second failure ends in `NEEDS_ATTENTION` with retained evidence.
5. Daily schedules survive backend restart and respect their configured timezone.
6. Duplicate overlapping runs for the same schedule scope are prevented.
7. Projects and run history can be run and deleted from their respective views.
8. Deletion provides confirmation and recoverable artifact handling.
9. Existing JSON cases and run history are importable into SQLite.
10. Outskill branding is visible and the interface contains no “enterprise” marketing copy.
11. All operational defaults and integrations are configuration-driven.
12. The critical frontend and backend validation suites pass.


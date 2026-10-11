# Group2 Showcase Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, task-by-task. One independent whole-branch review at completion.

**Goal:** A reproducible, deployable shop demonstrates actual generation, one-retry repair, and visual review, with useful Studio management and shareable evidence.

**Architecture:** FastAPI serves scenario-controlled static shop assets; SQLite persists switches. The Studio consumes the same-origin API; current n8n, Docker worker and paired Chromium paths remain authoritative.

**Tech Stack:** Python/FastAPI/SQLite, HTML/CSS/JS, Next.js 16/React, Playwright, n8n MCP, Pixelmatch, FFmpeg, Archify.

**Spec:** docs/superpowers/specs/2026-10-11-hackathon-showcase-design.md

## Global Constraints

- Synthetic accounts and shipping only; no real payments, no Kane CLI.
- n8n discovery for creation; saved scripts for replay; one repair retry maximum.
- No private env files or credentials in source, logs or published deliverables.
- Preserve independent functional/visual outcomes and immutable baseline.
- Video duration strictly under 120 seconds, disclose compression.

## Review Focus

- Localhost target inside Docker must work without rewriting saved script or host credentials.
- Changing one scenario must not affect another; partial switch updates preserve other settings.
- Authentication/business failures must not get falsely healed by removing assertions.
- Active run deletion must not race execution; completed deletion must remove audit references.
- Visual baseline/current must not disappear when source run evidence is deleted.

### Task 1: Deployable scenario shop

**Files:** backend/demo_shop/{index.html,shop.css,shop.js}; backend/api/demo_lab.py; backend/database.py; backend/runner.py; backend/tests/test_demo_lab.py; frontend/tests/browser/demo-shop.spec.ts.
**Interfaces:** Produces POST/GET `/api/demo-lab/scenarios`, PATCH `/api/demo-lab/scenarios/{id}` with `locator_revision: 0|1`, `visual_variant: bool`, `checkout_failure: bool`; GET `/api/demo-shop/{id}` and static assets. Isolated worker maps only loopback goto URLs to host.docker.internal.
- [ ] Add scenario CRUD/isolation/404/validation and Docker gateway tests; run pytest, expect RED missing routes/mapping.
- [ ] Implement bounded switches and semantically labeled shop with synthetic login/registration/cart/checkout; add browser tests of actual flows and rejected paths.
- [ ] Run backend pytest and browser demo-shop test, expect GREEN; commit task.

### Task 2: Studio management and visual evidence

**Files:** backend/api/system.py; backend/api/runs.py; backend/visual_review.py; backend/orchestrator.py; frontend/app/{page.tsx,demo-lab/page.tsx,runs/page.tsx,runs/[id]/page.tsx}; Sidebar.tsx; RunVisual.tsx; tests.
**Interfaces:** Consumes Task1 scenarios; produces GET `/api/overview` metrics; DELETE run rejects active409/missing404; review baseline/current/diff artifact IDs in Run.visual_review.
- [ ] Add metrics/deletion/visual persistence tests and frontend view tests; run focused tests, expect RED.
- [ ] Implement aggregate dashboard, Group2 badge, lab controls with target URL/objective, safe history deletion, retained comparison evidence.
- [ ] Run full backend/frontend suites, lint/build, expect GREEN; commit task.

### Task 3: Genuine showcase and architecture

**Files:** scripts/record_showcase.py; docs/hackathon/README.md; docs/hackathon/architecture.{json,html}; local artifacts/showcase video and receipts.
**Interfaces:** Consumes public Studio/API surfaces, real configured agents, scenario switches, persisted run evidence. Produces a real time-compressed walkthrough <120sec and evidence manifest with status/agent/run IDs, no private data.
- [ ] Run actual browser UI generation and saved replay with live n8n; induce locator, visual, and business failures; registration smoke test. Expected genuine audited invocations and repair retry or report concrete blocker honestly.
- [ ] Build Archify candidate from source, validate/deliver/visual-check and inspect screenshots; expected 9/9 showcase and no overflow.
- [ ] Record real browser stages, encode captioned video and verify duration; document URLs/deployment/gateway and reproduction; run full verification and commit.
- [ ] One whole-branch independent review; fix important findings RED→GREEN, then merge into demo_master and push within existing authorization.

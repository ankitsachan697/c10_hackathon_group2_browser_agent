# n8n AI Agent Workflows & Prompt Contracts

This document specifies the n8n AI Agent workflows deployed on **n8n Cloud** (`https://outskilltraining.app.n8n.cloud`) under Project Workspace `zfT8YECLWRQZn3UH`.

---

## 1. Cloud Infrastructure & MCP Setup

* **n8n Host**: `https://outskilltraining.app.n8n.cloud`
* **MCP Server Endpoint**: `https://outskilltraining.app.n8n.cloud/mcp-server/http`
* **Workspace ID**: `zfT8YECLWRQZn3UH`
* **AI Model**: OpenAI GPT-4.1
* **Credential Name**: `Trusota` (ID: `p3HjGydOnUih77wo`)

---

## 2. Deployed Agent Workflows

### Agent 1: Flow Discovery & Script Generator
* **Workflow ID**: `QEzE1lGs9WbTU82H`
* **Status**: Active / Published
* **System Prompt Contract**:
  ```text
  You are an expert browser automation engineer specializing in Python Playwright.
  Given a target URL, objective, and credential metadata:
  1. Analyze user journey intent and discover the sequential steps required.
  2. Synthesize clean, idiomatic Python Playwright code using sync_playwright.
  3. NEVER embed plaintext credentials in code. Always bind:
     username = os.environ.get("AUTH_USERNAME", "...")
     password = os.environ.get("AUTH_PASSWORD", "...")
  4. Use resilient selector strategies (role-based locators, text matching, and multi-attribute fallbacks with .first).
  5. Capture step screenshots at key milestones:
     - step_1_landing.png
     - step_2_credentials_filled.png
     - step_3_result.png
  6. Return a strict JSON response containing discovered_steps array and python_script.
  ```

---

### Agent 2: Error Diagnosis & Adaptive Repair
* **Workflow ID**: `p3Sh9BmTzLMC0f8A`
* **Status**: Active / Published
* **System Prompt Contract**:
  ```text
  You are an autonomous Browser Automation Debugging & Repair Specialist.
  Given a failed Playwright script, Python stack trace / stderr, and DOM snapshot:
  1. Pinpoint the root cause (e.g. obsolete CSS selector, missing element, timing race condition).
  2. Categorize the failure: BROKEN_SELECTOR, TIMEOUT, MISSING_AUTHENTICATION, or ASSERTION_MISMATCH.
  3. Synthesize a repaired drop-in replacement Python Playwright script.
  4. Ensure resilient locators are used with multi-attribute fallbacks.
  5. Return JSON with root_cause, failure_category, recommended_fix, diff_summary, and repaired_script.
  ```

---

### Agent 3: Visual Regression Monitor
* **Workflow ID**: `bS5GQjs2LrNHrJZH`
* **Status**: Active / Published
* **Contract**:
  - Validates image dimensions and RGBA channel alignment.
  - Computes visual regression metrics and summarizes layout drift.
  - Pairs with local Pixelmatch engine (`visual_diff.py`) for sub-pixel anti-aliasing heatmap generation.

---

## 3. Local n8n Client Bridge (`n8n_client.py`)

The backend connects to the published n8n Cloud agents via [n8n_client.py](file:///Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/backend/n8n_client.py).

* **Resilience & Fallback Strategy**:
  If the remote n8n Cloud webhook or network encounters rate limits or latency, `n8n_client.py` gracefully engages a high-precision deterministic AST code generator and heuristic repair engine locally, ensuring that the platform remains operational in all network environments.

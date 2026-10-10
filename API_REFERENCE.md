# API Reference: AI Self-Healing Browser Automation Engine

Base URL: `http://127.0.0.1:8000`

---

## 1. System Health & Probes

### `GET /api/health`
Returns backend service availability and connectivity to n8n Cloud.

* **Response**:
  ```json
  {
    "status": "healthy",
    "timestamp": 1791647907.9,
    "runner_ready": true,
    "n8n_connected": true
  }
  ```

### `WebSocket /ws/session` & `GET /ws/session`
Telemetry socket endpoint for browser extensions and live session probes.
* **WebSocket**: Emits and receives JSON heartbeats (`{"status": "active"}`).
* **HTTP Fallback**: Returns `{"status": "active", "websocket_available": true}`.

---

## 2. Test Execution & Automation

### `POST /api/execute-script`
**Direct Script Validation**: Executes the exact Python Playwright script provided in the request body. If the run fails, the backend invokes the Error Diagnosis & Adaptive Repair Agent automatically to patch and re-verify the script.

* **Request Body**:
  ```json
  {
    "script": "import os\nfrom playwright.sync_api import sync_playwright...",
    "url": "https://practicetestautomation.com/practice-test-login/",
    "test_name": "PracticeTest Automation Login",
    "headed": false,
    "username": "student",
    "password": "Password123",
    "timeout_seconds": 45,
    "auto_heal": true
  }
  ```

* **Response**:
  ```json
  {
    "run_id": "run_1791647346_77518a",
    "status": "PASSED",
    "passed": true,
    "execution_result": {
      "exit_code": 0,
      "duration_seconds": 7.84,
      "screenshots": ["step1_login.png", "step2_logged_in.png"],
      "video": "session_video.webm",
      "stdout": "...",
      "stderr": ""
    },
    "final_script": "...",
    "healed_script": null,
    "healing_history": [],
    "visual_regression": {
      "status": "BASELINE_ESTABLISHED",
      "passed": true,
      "is_first_run": true,
      "summary": "🌟 Golden Baseline established..."
    },
    "logs": [ ... ]
  }
  ```

---

### `POST /api/autonomous-run`
**Full End-to-End Autonomous Pipeline**:
1. Invokes Flow Discovery & Script Generator Agent on n8n Cloud.
2. Executes synthesized Playwright script in Chromium.
3. If failure occurs, executes Error Diagnosis & Adaptive Repair loop (up to `max_repair_attempts`).
4. Performs Visual Regression check against Golden Baseline.
5. Saves run telemetry to Run History.

* **Request Body**:
  ```json
  {
    "url": "https://practicetestautomation.com/practice-test-login/",
    "task_objective": "Perform user authentication with student and Password123, then validate 'Logged In Successfully' heading.",
    "username": "student",
    "password": "Password123",
    "max_repair_attempts": 3,
    "run_visual_regression": true,
    "headed": false,
    "test_case_name": "PracticeTest Login Journey"
  }
  ```

* **Response**:
  ```json
  {
    "run_id": "run_1791647064_18d7ac",
    "success": true,
    "attempts": 1,
    "discovered_steps": [
      "Navigate to target URL",
      "Fill username and password fields",
      "Click Submit button",
      "Assert 'Logged In Successfully' heading"
    ],
    "final_script": "...",
    "execution_result": { ... },
    "healing_history": [ ... ],
    "visual_regression": { ... },
    "logs": [ ... ]
  }
  ```

---

## 3. Standalone Agent Endpoints

### `POST /api/discovery-and-generate`
Invokes Agent 1 on n8n Cloud to discover user journey steps and generate a resilient Playwright script.

* **Request Body**:
  ```json
  {
    "url": "https://example.com/login",
    "task_objective": "Log in with test account and navigate to profile",
    "credentials_meta": { "has_auth": true }
  }
  ```

* **Response**:
  ```json
  {
    "status": "SUCCESS",
    "target_url": "https://example.com/login",
    "discovered_steps": ["1. Load login page", "2. Input credentials", "3. Submit"],
    "python_script": "..."
  }
  ```

---

### `POST /api/diagnose-and-repair`
Invokes Agent 2 on n8n Cloud to analyze an execution error, determine root cause, and synthesize a repaired script.

* **Request Body**:
  ```json
  {
    "original_script": "...",
    "error_trace": "playwright._impl._errors.TimeoutError: Timeout waiting for locator('button#submit')",
    "dom_snapshot": "<html>...</html>",
    "screenshot_path": "failure_screenshot.png"
  }
  ```

* **Response**:
  ```json
  {
    "status": "REPAIRED",
    "failure_category": "BROKEN_SELECTOR_OR_TIMEOUT",
    "root_cause": "The selector button#submit is obsolete; matching button with type='submit' found in DOM.",
    "recommended_fix": "Use role-based selector page.get_by_role('button', name='Submit') with fallback.",
    "diff_summary": "Replaced button#submit with resilient multi-attribute locator.",
    "repaired_script": "..."
  }
  ```

---

### `POST /api/visual-diff`
Invokes Pixelmatch image comparison between baseline and candidate screenshots.

* **Request Body**:
  ```json
  {
    "baseline_path": "artifacts/baselines/test_1/golden_result.png",
    "candidate_path": "artifacts/run_123/step_3_result.png",
    "threshold": 0.1,
    "tolerance_percent": 0.5
  }
  ```

* **Response**:
  ```json
  {
    "status": "COMPLETED",
    "passed": true,
    "total_pixels": 921600,
    "mismatched_pixels": 42,
    "mismatch_percentage": 0.005,
    "tolerance_threshold": 0.5,
    "diff_image_path": ".../visual_diff.png",
    "diff_image_filename": "diff_1791647900.png",
    "summary": "Visual check PASSED with 0.01% shift (below 0.5% tolerance)."
  }
  ```

---

## 4. Test Suites & Projects Management

### `GET /api/test-cases`
Returns all saved test cases grouped across projects.

* **Response**:
  ```json
  {
    "cases": [
      {
        "id": "tc_practice_login",
        "project": "Authentication",
        "name": "PracticeTest Automation Login",
        "target_url": "https://practicetestautomation.com/practice-test-login/",
        "objective": "Perform user authentication with student/Password123 and validate Logged In Successfully",
        "username": "student",
        "password_masked": "••••••••",
        "schedule": "Manual",
        "created_at": "2026-10-10 21:00:08",
        "last_run_status": "PASSED",
        "has_baseline": true
      }
    ]
  }
  ```

### `POST /api/test-cases`
Saves or updates a test case definition in `test_suites/cases.json`.

* **Request Body**:
  ```json
  {
    "project": "Authentication",
    "name": "PracticeTest Login Validation",
    "target_url": "https://practicetestautomation.com/practice-test-login/",
    "objective": "Authenticate student/Password123 and assert success",
    "script": "...",
    "username": "student",
    "schedule": "Daily at Midnight (00:00 UTC)"
  }
  ```

### `DELETE /api/test-cases/{case_id}`
Deletes a test case by ID.

### `POST /api/test-cases/{case_id}/run?headed={bool}`
Executes a saved test case directly and records the run in Run History.

---

## 5. Run History & Artifacts

### `GET /api/runs`
Returns the execution history list (last 100 runs) with timestamps, durations, statuses, screenshots, and video references.

### `GET /api/artifacts/{file_path:path}`
Universal artifact server. Supports:
- Step screenshots (`.png`, `.jpg`)
- Pixelmatch visual diff heatmaps (`visual_diff.png`)
- Golden Baselines (`baselines/{slug}/golden_result.png`)
- Playwright WebM Session Videos (`session_video.webm` with byte-range streaming support)

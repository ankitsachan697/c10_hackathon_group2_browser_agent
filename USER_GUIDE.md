# User & Operator Guide: AI Self-Healing Browser Automation Platform

Welcome to the AI Self-Healing Browser Automation System. This guide walks you through the features of the platform, running your first automated journey, monitoring self-healing, organizing test suites, and viewing visual regression heatmaps.

---

## 1. Quick Launch

### Start the Platform
1. **Backend Server** (runs on port 8000):
   ```bash
   cd /Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/backend
   python3 server.py
   ```
   *(Note: `server.py` automatically detects and uses the local `.venv` virtual environment).*

2. **Frontend Dashboard** (runs on port 3000):
   ```bash
   cd /Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/frontend
   npm run dev
   ```
3. Open your browser at **`http://localhost:3000`**.

---

## 2. Platform Layout Walkthrough

The platform uses a split-panel dashboard layout:

```
+-----------------------------------------------------------------------------------------+
| [AUTONOMOUS BROWSER AGENTS] Presets: [🎯 PracticeTest] [🔐 Generic Login] [🔥 Broken]  |
+--------------------------+--------------------------------------------------------------+
| LEFT SIDE PANEL          | MAIN WORKSPACE                                               |
| [📁 Projects] [📜 History]| 1. Active Agent Status Deck (Discovery, Exec, Diagnosis...) |
|                          | 2. Journey Configuration Deck (URL, Credentials, Mode, Run) |
| - Project Folders:       | 3. Live Log Terminal (Left) | Script Viewer/Editor (Right)   |
|   📁 Authentication      | 4. Visual Regression Monitor & Playwright Session Video      |
|   📁 Checkout            | 5. Step Screenshots Carousel (Click to Zoom)                 |
|   ...                    |                                                              |
+--------------------------+--------------------------------------------------------------+
```

---

## 3. Running Your First Test Journey

### Step 1: Use the PracticeTest Preset
1. Click the **"🎯 PracticeTest (student/Password123)"** preset button in the top navigation bar.
2. The form fills automatically:
   - **Target URL**: `https://practicetestautomation.com/practice-test-login/`
   - **Username**: `student`
   - **Password**: `Password123` (shielded by default)
   - **Objective**: Authenticate and validate the `Logged In Successfully` heading.

### Step 2: Choose Headed vs. Headless Mode
- **⚡ HEADLESS (BACKGROUND)**: Runs fast in the background without opening a visible browser window.
- **🖥️ HEADED (WATCH BROWSER LIVE)**: Opens a physical Chromium window on macOS with slow-motion execution (`slow_mo=600ms`) so you can visually watch the bot type credentials and navigate pages.

### Step 3: Click "START TASK"
- Watch the **Agent Status Cards** animate through:
  1. *Flow Discovery Agent* (analyzes forms & pages).
  2. *Script Generator Agent* (synthesizes Python Playwright code).
  3. *Execution Agent* (launches Chromium & logs events with credential redaction).
  4. *Visual Regression Monitor* (captures screenshots and manages Golden Baseline).

---

## 4. Direct Script Execution & In-Viewer Code Editing

You don't need to generate a new script every time:
1. In the **Playwright Script Viewer** (right panel), click **"Edit Code"**.
2. The viewer turns into an in-browser code editor. You can:
   - Tweak locators or timeouts.
   - Add custom assertions (e.g. `expect(page.locator("h1")).to_have_text(...)`).
   - Add custom screenshots (e.g. `page.screenshot(path="custom_step.png")`).
3. Click **"▶ Run Script to Validate"**:
   - The platform immediately sends the customized script to the Playwright runner.
   - Output logs stream in the terminal.
   - Screenshots and session video are updated.
   - If your customized code contains errors, the **Error Diagnosis & Adaptive Repair Agent** automatically triggers to fix it for you.

---

## 5. Test Suites & Project Folders

### Saving a Script to a Test Suite
1. Once a script is generated or edited, click **"Save Suite"** in the script viewer header.
2. Enter:
   - **Project / Folder Name** (e.g. `Authentication`, `Checkout`, `Regression`).
   - **Test Case Name** (e.g. `PracticeTest Login Journey`).
   - **Run Schedule** (e.g. `Manual`, `Hourly`, `Daily at Midnight`).
3. Click **"Save to Suite"**.

### Running from the Left Side Panel
1. Click the **"Projects"** tab in the left side panel.
2. Expand your project folder.
3. Click **"▶ Run"** next to any saved test case to execute it with 1 click.
4. Click **"👁 Load"** to load the script into the editor for review or modification.

---

## 6. Inspecting Run History & Playing Session Videos

1. Click the **"History"** tab in the left side panel.
2. Click any past execution run from the chronological list:
   - The main workspace updates to show that specific run.
   - The **Playwright Session Video Recording (.webm)** player loads with full controls (Play/Pause, Seek, Fullscreen, Volume).
   - Milestone screenshots captured during that run are displayed below.
   - Click any screenshot to open the **High-Resolution Click-to-Zoom Modal**.

---

## 7. Understanding the Smart Golden Baseline

* **Run 1**: The first time you execute a test for a URL/case, the milestone screenshot is locked as the master **Golden Baseline**.
  - Badge displayed: **`🌟 GOLDEN BASELINE ESTABLISHED`**.
  - No false regression warnings are triggered.
* **Run 2+**: Subsequent executions compare newly captured screenshots against the Golden Baseline using **Pixelmatch**:
  - If layout elements moved or changed, the **Magenta Diff Heatmap** highlights exact pixel deviations.
  - Pixel shift percentage and tolerance threshold (default: 0.5%) are displayed.
  - Tabs allow you to switch between **Magenta Diff Heatmap**, **Golden Baseline**, and **Current Candidate** for side-by-side comparison.

---

## 8. Testing Self-Healing with the "Broken Selector" Preset

To see the autonomous self-healing loop in action:
1. Click the **"🔥 Broken Selector (Test Heal)"** preset button in the top navigation.
2. Click **"START TASK"**.
3. What happens:
   - The initial script attempts to click an obsolete button (`button#legacy-submit-v1`).
   - Execution fails with a timeout error.
   - The **Error Diagnosis Agent** analyzes the traceback and DOM snapshot.
   - The **Adaptive Repair Agent** synthesizes a healed selector using resilient fallback locators.
   - The repaired script re-executes automatically and finishes with status **PASSED**!
   - In the script viewer, click the **"Healed Script"** and **"Diagnosis Report"** tabs to inspect the root-cause analysis and code diff.

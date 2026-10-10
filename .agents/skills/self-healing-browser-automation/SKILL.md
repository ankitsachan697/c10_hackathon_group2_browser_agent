---
name: self-healing-browser-automation
description: Operational cheatsheet and engineering skill for developing, operating, and extending the AI Self-Healing Browser Automation System (Python Playwright, n8n Cloud AI Agents, Pixelmatch Visual Regression, Next.js Control Panel).
---

# Self-Healing Browser Automation Skill

This skill provides guidelines, command references, and architectural patterns for interacting with, testing, and extending the **AI Self-Healing Browser Automation System**.

---

## 1. Directory Structure

```
/browser-agent-platform/
├── backend/
│   ├── .venv/                   # Python virtual environment
│   ├── runner.py                # Subprocess Playwright runner with secret redactor
│   ├── visual_diff.py           # Pixelmatch RGBA diff engine
│   ├── n8n_client.py            # n8n Cloud MCP integration & local fallback
│   ├── test_suite_manager.py    # Test suites, project folders & Golden Baseline manager
│   ├── server.py                # FastAPI REST & WebSocket server
│   └── test_suites/             # cases.json and runs_history.json
├── frontend/
│   ├── app/                     # Next.js 14 App Router (page.tsx, layout.tsx)
│   └── components/
│       ├── SidebarProjectsAndHistory.tsx  # Left side panel (Projects & Run History)
│       ├── ScriptDiffViewer.tsx           # Playwright script viewer/editor & validation
│       ├── VisualRegressionViewer.tsx     # Pixelmatch heatmap & session video player
│       ├── LiveLogTerminal.tsx            # Streaming log viewer with auto-scroll
│       └── AgentStatusCards.tsx           # Multi-agent activity badges
└── artifacts/
    ├── baselines/               # Locked Golden Baselines per test slug
    └── run_*/                   # Timestamped run folders with screenshots & video.webm
```

---

## 2. Server & Runner Commands

### Starting the Backend
```bash
cd /Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/backend
# server.py auto-redirects to .venv if run with system python
python3 server.py
# Or explicitly:
.venv/bin/python server.py
```

### Starting the Frontend
```bash
cd /Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/frontend
npm run dev
# Production build check:
npm run build
```

---

## 3. Playwright Script Generation Rules

When writing or generating Python Playwright automation scripts:
1. **Never Hardcode Secrets**:
   Always parameterize user credentials:
   ```python
   username = os.environ.get("AUTH_USERNAME", "default_user")
   password = os.environ.get("AUTH_PASSWORD", "")
   ```
2. **Resilient Locator Fallbacks**:
   Avoid brittle single-ID selectors (`button#submit-v1`). Use resilient fallbacks:
   ```python
   page.locator("button[type='submit'], button:has-text('Submit'), button#submit").first.click()
   ```
3. **Capture Milestone Screenshots**:
   ```python
   page.screenshot(path="step_1_landing.png")
   page.screenshot(path="step_2_credentials_filled.png")
   page.screenshot(path="step_3_result.png")
   ```
4. **Flushing Video Recordings**:
   To ensure video is written to disk and avoid 0-byte corruptions, always close the `BrowserContext` explicitly:
   ```python
   context = browser.new_context(record_video_dir=run_dir, record_video_size={"width": 1280, "height": 800})
   page = context.new_page()
   try:
       # Actions ...
   finally:
       context.close()
       browser.close()
   ```

---

## 4. Troubleshooting & Operational Tips

### Port 8000 Already in Use (`[Errno 48]`)
If port 8000 cannot be bound:
1. Check for background Docker containers forwarding port 8000:
   ```bash
   docker ps | grep 8000
   docker stop <container_name>
   ```
2. Kill any stale Python listener:
   ```bash
   kill -9 $(lsof -ti :8000) 2>/dev/null || true
   ```

### Hydration Errors in Next.js
Browser extensions (such as color checkers or password managers) often inject attributes (`class="aqua-ext-enabled"`) into `<body>`.
Always ensure `suppressHydrationWarning` is present on both `<html>` and `<body>` in `frontend/app/layout.tsx`.

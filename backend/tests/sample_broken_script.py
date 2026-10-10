"""
Sample broken Playwright script to test Error Diagnosis & Adaptive Repair Agent.
Contains an outdated/broken CSS selector that will fail with a TimeoutError.
"""

import os
import sys
from playwright.sync_api import sync_playwright

def test_broken_flow():
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", "./artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    print("[Broken Flow Test] Starting Playwright test...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("[Broken Flow Test] Navigating to https://example.com...")
        page.goto("https://example.com", wait_until="domcontentloaded")
        page.screenshot(path=os.path.join(artifacts_dir, "step_1_landing.png"))

        try:
            # Intentionally broken button selector (does not exist on example.com)
            print("[Broken Flow Test] Attempting to click obsolete locator: 'button#legacy-submit-v1'...")
            page.locator("button#legacy-submit-v1").click(timeout=3000)
        except Exception as e:
            print(f"[Broken Flow Test] Error caught: {e}", file=sys.stderr)
            # Diagnostic artifacts
            page.screenshot(path=os.path.join(artifacts_dir, "failure_screenshot.png"))
            with open(os.path.join(artifacts_dir, "dom_snapshot.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    test_broken_flow()

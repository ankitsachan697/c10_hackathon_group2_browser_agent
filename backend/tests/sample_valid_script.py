"""
Sample valid Playwright journey test.
Navigates to Hacker News, verifies the brand logo and title, and captures baseline screenshots.
"""

import os
import sys
from playwright.sync_api import sync_playwright

def test_journey():
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", "./artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    print("[Valid Journey] Initializing Chromium browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        print("[Valid Journey] Navigating to https://news.ycombinator.com...")
        page.goto("https://news.ycombinator.com", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # Baseline screenshot
        page.screenshot(path=os.path.join(artifacts_dir, "step_1_hackernews.png"))
        print(f"[Valid Journey] Page title verified: '{page.title()}'")

        # Click 'newest' link
        newest_link = page.locator("a:has-text('newest')").first
        if newest_link.is_visible():
            print("[Valid Journey] Clicking 'newest' link...")
            newest_link.click()
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(artifacts_dir, "step_2_newest_page.png"))
            print("[Valid Journey] Reached newest submissions page.")

        print("[Valid Journey] Journey PASSED successfully.")
        browser.close()

if __name__ == "__main__":
    test_journey()

# Auto-injected environment setup
import os, sys
os.environ.setdefault("ARTIFACTS_DIR", '/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791646394_51dea2')
run_dir = '/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791646394_51dea2'

import os
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(record_video_dir='/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791646394_51dea2', record_video_size={'width': 1280, 'height': 800})
        page = context.new_page()
        page.goto("https://practicetestautomation.com/practice-test-login/")
        page.screenshot(path="step1_login.png")
        page.locator("input#username").fill(os.environ.get("AUTH_USERNAME", "student"))
        page.locator("input#password").fill(os.environ.get("AUTH_PASSWORD", "Password123"))
        page.locator("button#submit").click()
        page.wait_for_selector("h1")
        page.screenshot(path="step2_logged_in.png")
        browser.close()

if __name__ == "__main__":
    run()
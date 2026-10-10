# Auto-injected environment setup
import os, sys
os.environ.setdefault("ARTIFACTS_DIR", '/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791643645_2a7839')
run_dir = '/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791643645_2a7839'


from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://example.com')
    # Intentionally broken selector that will timeout
    page.locator('button#non-existent-button-id').click(timeout=3000)
    browser.close()

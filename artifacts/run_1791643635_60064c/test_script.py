# Auto-injected environment setup
import os, sys
os.environ.setdefault("ARTIFACTS_DIR", '/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791643635_60064c')
run_dir = '/Users/asacha/Downloads/ai-accelerator-C10/browser-agent-platform/artifacts/run_1791643635_60064c'


import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://example.com')
    artifacts_dir = os.environ.get('ARTIFACTS_DIR', '.')
    page.screenshot(path=os.path.join(artifacts_dir, 'example_screenshot.png'))
    print('Testing sensitive secret printing: my_secret_password_1234')
    browser.close()

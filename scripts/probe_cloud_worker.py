"""Manual, synthetic headless proof using scoped local Vercel OIDC credentials.

No application history or controller snapshot is copied to the worker.
Requires `vercel env pull` in frontend first. Prints only nonsecret evidence.
"""
import asyncio
import base64
import json
import os
import tempfile
import time
from subprocess import CalledProcessError
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values
from backend.sandbox_transport import SandboxTransport
from backend.sandbox_runner import SandboxPlaywrightRunner


async def main():
    config = json.loads(Path("config/application.json").read_text())["cloud"]
    token = dotenv_values("frontend/.env.local").get("VERCEL_OIDC_TOKEN", "")
    part = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    assert claims["owner_id"] == config["teamId"] and claims["project_id"] == config["projectId"]

    def credentials(minimum_lifetime=0):
        assert claims["exp"] > time.time() + minimum_lifetime, "Refresh local Vercel OIDC credentials first"
        return {"token": token, "team_id": config["teamId"], "project_id": config["projectId"]}

    policy = SimpleNamespace(origin="", sdk_credentials=credentials)
    destination = Path(tempfile.mkdtemp(prefix="group2-cloud-proof-"))
    runner = SandboxPlaywrightRunner(str(destination), SandboxTransport(policy, config["controllerImage"]))
    code = '''import os
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://practicetestautomation.com/practice-test-login/", wait_until="domcontentloaded")
    page.get_by_label("Username").fill(os.environ["AUTH_USERNAME"])
    page.get_by_label("Password").fill(os.environ["AUTH_PASSWORD"])
    page.get_by_role("button", name="Submit").click()
    expect(page.get_by_role("heading", name="Logged In Successfully")).to_be_visible()
    page.screenshot(path=os.path.join(os.environ["ARTIFACTS_DIR"], "proof.png"))
    browser.close()
'''
    try:
        result = await runner.execute_script(code, target_url="https://practicetestautomation.com/practice-test-login/", timeout_seconds=60,
                                             env_vars={"AUTH_USERNAME": "student", "AUTH_PASSWORD": "Password123"},
                                             on_log=lambda item: print(item["message"], flush=True))
    except CalledProcessError as error:
        # Installation happens before any application secret reaches the VM.
        print(str(error.stdout or "")[-5000:], str(error.stderr or "")[-5000:])
        raise
    print(json.dumps({key: result[key] for key in ("passed", "exit_code", "duration_seconds", "run_dir", "screenshots", "video")}))
    assert result["passed"] and result["screenshots"] and result["video"]


if __name__ == "__main__":
    asyncio.run(main())

from backend.runner import PlaywrightRunner
import pytest


def test_wrapper_routes_chromium_launch_through_configurable_cdp_endpoint(tmp_path):
    runner = PlaywrightRunner(tmp_path, cdp_endpoint="wss://browser.example.test/session", cdp_timeout_seconds=12)
    wrapped = runner._wrap_script(
        "with sync_playwright() as p:\n    browser = p.chromium.launch(headless=True)\n",
        str(tmp_path / "run"),
    )

    assert "_connect_or_launch(p.chromium, headless=True)" in wrapped
    assert "connect_over_cdp(endpoint, timeout=timeout_ms)" in wrapped
    assert "PLAYWRIGHT_CDP_ENDPOINT" in wrapped


def test_wrapper_keeps_local_launch_fallback(tmp_path):
    runner = PlaywrightRunner(tmp_path)
    wrapped = runner._wrap_script(
        "with sync_playwright() as p:\n    browser = p.chromium.launch()\n",
        str(tmp_path / "run"),
    )

    assert "return browser_type.launch(*args, **kwargs)" in wrapped


def test_wrapper_preserves_browser_close_indentation(tmp_path):
    runner = PlaywrightRunner(tmp_path)
    wrapped = runner._wrap_script(
        "def run():\n    with manager():\n        try:\n            pass\n        finally:\n            browser.close()\n",
        str(tmp_path / "run"),
    )

    compile(wrapped, "wrapped.py", "exec")


def test_execution_environment_does_not_inherit_backend_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("N8N_BEARER_TOKEN", "must-not-leak")
    monkeypatch.setenv("PATH", "/usr/bin")
    runner = PlaywrightRunner(tmp_path)

    environment = runner._execution_environment({"SAFE_VALUE": "allowed"}, tmp_path)

    assert environment["SAFE_VALUE"] == "allowed"
    assert environment["PATH"] == "/usr/bin"
    assert "N8N_BEARER_TOKEN" not in environment


@pytest.mark.asyncio
async def test_runner_redacts_username_and_password_from_all_output(tmp_path):
    runner = PlaywrightRunner(tmp_path)
    script = "print('student'); import sys; print('Password123', file=sys.stderr)"

    result = await runner.execute_script(
        script, env_vars={"AUTH_USERNAME": "student", "AUTH_PASSWORD": "Password123"},
        secrets=["student", "Password123"], timeout_seconds=10,
    )

    rendered = str(result)
    assert "student" not in rendered
    assert "Password123" not in rendered

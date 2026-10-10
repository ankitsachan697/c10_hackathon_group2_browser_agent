from backend.runner import PlaywrightRunner, UnsafeScriptError, validate_browser_script
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
    runner = PlaywrightRunner(tmp_path, allow_unsafe_local_execution=True)
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


def test_wrapper_handles_empty_context_and_injects_credential_mask_before_page(tmp_path):
    wrapped = PlaywrightRunner(tmp_path)._wrap_script(
        "with sync_playwright() as p:\n    browser = p.chromium.launch()\n    context = browser.new_context()\n    page = context.new_page()\n",
        str(tmp_path / "run"),
    )
    compile(wrapped, "wrapped.py", "exec")
    assert "new_context(," not in wrapped
    assert wrapped.index("context.add_init_script") < wrapped.index("page = context.new_page()")


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
    runner = PlaywrightRunner(tmp_path, allow_unsafe_local_execution=True)
    script = "print('student'); import sys; print('Password123', file=sys.stderr)"

    result = await runner.execute_script(
        script, env_vars={"AUTH_USERNAME": "student", "AUTH_PASSWORD": "Password123"},
        secrets=["student", "Password123"], timeout_seconds=10,
    )

    rendered = str(result)
    assert "student" not in rendered
    assert "Password123" not in rendered


@pytest.mark.parametrize("script", [
    "import subprocess\nsubprocess.run(['id'])",
    "import socket\nsocket.create_connection(('example.com', 80))",
    "open('/etc/passwd').read()",
    "().__class__.__mro__",
])
def test_script_policy_blocks_host_escape_primitives(script):
    with pytest.raises(UnsafeScriptError):
        validate_browser_script(script)


def test_script_policy_allows_playwright_and_scoped_artifacts():
    validate_browser_script("import os\nfrom playwright.sync_api import sync_playwright\nos.makedirs(os.path.join(os.environ.get('ARTIFACTS_DIR'), 'shots'))")


def test_container_worker_has_os_isolation_and_only_run_mount(tmp_path):
    runner = PlaywrightRunner(tmp_path, container_image="runner:test")
    environment = runner._execution_environment({"AUTH_PASSWORD": "secret"}, "/work")
    command = runner._worker_command(str(tmp_path / "run/test_script.py"), str(tmp_path / "run"), environment)

    rendered = " ".join(command)
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert "dst=/work" in rendered
    assert str(tmp_path / "run") in rendered
    assert "AUTH_PASSWORD" in command
    assert "secret" not in rendered
    assert "--name" in command


def test_host_execution_requires_explicit_local_opt_in(tmp_path):
    runner = PlaywrightRunner(tmp_path)
    with pytest.raises(UnsafeScriptError, match="host execution is disabled"):
        runner._worker_command("script.py", str(tmp_path), {})

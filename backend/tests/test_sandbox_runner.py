import json
from pathlib import Path

import pytest

from backend.sandbox_runner import SandboxPlaywrightRunner
from backend.sandbox_transport import WorkerResult
from backend.action_events import MARKER


SCRIPT = '''import os
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://example.com/")
    page.screenshot(path=os.path.join(os.environ["ARTIFACTS_DIR"], "home.png"))
    browser.close()
'''


class Transport:
    def __init__(self, failure=None, exit_code=0):
        self.calls = []
        self.failure = failure
        self.exit_code = exit_code

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["on_stdout"](MARKER + json.dumps({"action": "navigate", "phase": "finished", "value": "synthetic-password"}))
        kwargs["on_stderr"]("password=synthetic-password")
        if self.failure:
            raise self.failure
        return WorkerResult(self.exit_code, {"home.png": b"PNG", "page@synthetic.webm": b"V" * 600, "dom_snapshot.html": b"synthetic-password"})


@pytest.mark.asyncio
async def test_worker_has_only_approved_auth_and_run_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("N8N_BEARER_TOKEN", "private-controller-token")
    transport = Transport()
    runner = SandboxPlaywrightRunner(str(tmp_path), transport)
    actions, logs = [], []
    result = await runner.execute_script(SCRIPT, target_url="https://example.com/", env_vars={"AUTH_USERNAME": "synthetic", "AUTH_PASSWORD": "synthetic-password", "N8N_BEARER_TOKEN": "must-not-transfer"}, timeout_seconds=60, on_action=actions.append, on_log=logs.append)
    call = transport.calls[0]
    assert call["environment"] == {"AUTH_USERNAME": "synthetic", "AUTH_PASSWORD": "synthetic-password", "ARTIFACTS_DIR": "/vercel/sandbox/work", "PYTHONUNBUFFERED": "1"}
    assert "private-controller-token" not in call["code"]
    assert "must-not-transfer" not in str(call)
    assert result["passed"]
    assert result["video"] == "session_video.webm"
    assert "synthetic-password" not in str(logs + actions) + result["dom_snapshot"]


@pytest.mark.asyncio
async def test_nonzero_exit_is_failure(tmp_path):
    result = await SandboxPlaywrightRunner(str(tmp_path), Transport(exit_code=1)).execute_script(SCRIPT, target_url="https://example.com/", timeout_seconds=60)
    assert result["passed"] is False
    assert result["status"] == "FAILED"


@pytest.mark.asyncio
async def test_headed_cloud_does_not_silently_fall_back(tmp_path):
    transport = Transport()
    with pytest.raises(ValueError, match="Headed"):
        await SandboxPlaywrightRunner(str(tmp_path), transport).execute_script(SCRIPT, headed=True, target_url="https://example.com/", timeout_seconds=60)
    assert not transport.calls


@pytest.mark.asyncio
async def test_artifacts_cannot_escape_output_directory(tmp_path):
    class BadTransport(Transport):
        async def execute(self, **kwargs):
            return WorkerResult(0, {"../outside.png": b"data"})
    with pytest.raises(ValueError, match="artifact"):
        await SandboxPlaywrightRunner(str(tmp_path), BadTransport()).execute_script(SCRIPT, target_url="https://example.com/", timeout_seconds=60)
    assert not (tmp_path.parent / "outside.png").exists()


def test_discovery_inspection_is_isolated(tmp_path):
    class InspectorTransport(Transport):
        async def execute(self, **kwargs):
            assert kwargs["environment"] == {"PYTHONUNBUFFERED": "1"}
            assert "AUTH_PASSWORD" not in kwargs["code"]
            kwargs["on_stdout"](json.dumps({"controls": '<button id="submit">Submit</button>'}))
            return WorkerResult(0, {})
    assert "Submit" in SandboxPlaywrightRunner(str(tmp_path), InspectorTransport()).inspect_target_controls("https://example.com/")


def test_worker_does_not_inherit_controller_snapshot():
    from backend.sandbox_transport import worker_create_options
    options = worker_create_options("pinned-clean-image", 180)
    assert options["persistent"] is False
    assert options["image"] == "pinned-clean-image"
    assert "source" not in options and "mounts" not in options
    assert options["env"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [TimeoutError(), ValueError("malformed stream")])
async def test_worker_stops_on_timeout_or_parse_error(tmp_path, failure):
    from backend.sandbox_transport import managed_worker
    class Box:
        destroyed = False
        async def destroy(self, **kwargs):
            self.destroyed = True
    box = Box()
    async def create(**kwargs):
        return box
    with pytest.raises(type(failure)):
        async with managed_worker(create, "clean-image", 180) as value:
            assert value is box
            raise failure
    assert box.destroyed


@pytest.mark.asyncio
async def test_browser_install_uses_same_python_and_home_as_execution():
    from backend.sandbox_transport import prepare_worker, trust_worker_proxy
    calls = []
    class Box:
        async def run_process(self, *args, **kwargs):
            calls.append((args, kwargs))
    await prepare_worker(Box())
    await trust_worker_proxy(Box())
    assert len(calls) == 7
    assert calls[0][0][0] == "sysctl" and calls[0][1]["sudo"]
    assert calls[1][0] == ("ip", ["-6", "route", "show"])
    assert not calls[3][1].get("sudo") and not calls[4][1].get("sudo")
    assert calls[4][0][1] == ["-m", "playwright", "install", "--with-deps", "chromium"]
    assert "https://" in calls[2][0][1][1]
    assert calls[5][0] == ("apt-get", ["install", "-y", "libnss3-tools"])
    assert "vercel-proxy-ca.pem" in calls[6][0][1][1]
    assert "certutil" in calls[6][0][1][1]


@pytest.mark.asyncio
async def test_stream_reads_bounded_chunks_and_rejects_output_flood():
    from backend.sandbox_transport import stream_worker_output
    class Reader:
        async def read(self, size):
            assert size <= 8192
            return "x" * size
    with pytest.raises(ValueError, match="message size"):
        await stream_worker_output(Reader(), lambda line: None, {"bytes": 0, "messages": 0})
    class Lines:
        async def read(self, size):
            return "x\n" * 4000
    with pytest.raises(ValueError, match="output limit"):
        await stream_worker_output(Lines(), lambda line: None, {"bytes": 0, "messages": 0})


def test_collector_cannot_load_worker_python_startup_modules():
    from backend.sandbox_transport import collector_command
    command, args = collector_command("print('manifest')")
    assert command == "/usr/bin/setpriv"
    assert args[:4] == ["--no-new-privs", "/usr/bin/python3", "-I", "-S"]


def test_manifest_rejects_file_flood_before_serializing(tmp_path, capsys):
    from backend.sandbox_transport import artifact_manifest_code
    for index in range(101): (tmp_path / f"{index}.png").write_bytes(b"x")
    with pytest.raises(ValueError, match="collection limit"):
        exec(artifact_manifest_code(str(tmp_path)), {})
    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_actual_artifact_reads_share_aggregate_budget():
    from backend.sandbox_transport import read_artifact, MAX_TOTAL
    class Reader:
        async def read(self, size): return b"x" * size
    with pytest.raises(ValueError, match="aggregate"):
        await read_artifact(Reader(), {"bytes": MAX_TOTAL - 5})

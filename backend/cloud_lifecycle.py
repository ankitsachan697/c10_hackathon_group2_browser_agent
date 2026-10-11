"""Controller state layout and single-PID bootstrap, independent of source releases."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def prepare_state(state_root: Path) -> None:
    for directory in (state_root, state_root / "artifacts", state_root / "artifacts/.trash"):
        if directory.is_symlink():
            raise ValueError("Controller state must not be a symlink")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)


def _health(secret: str) -> dict | None:
    try:
        request = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"x-studio-control": secret})
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def ensure_runtime(release_root: Path, state_root: Path, run_command=None) -> Path:
    run_command = run_command or subprocess.run
    requirements = release_root / "backend/requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    runtime_python = state_root / "runtime-venv/bin/python"
    marker = state_root / "requirements.sha256"
    if not runtime_python.exists():
        run_command([sys.executable, "-m", "venv", str(state_root / "runtime-venv")], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    if not marker.exists() or marker.read_text() != digest:
        run_command([str(runtime_python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=150)
        marker.write_text(digest)
    return runtime_python


def _registered_process_alive(pid_file: Path, session_id: str = "") -> bool:
    if pid_file.is_symlink():
        raise ValueError("Registered PID file must not be a symlink")
    if not pid_file.exists():
        return False
    session_file = pid_file.parent / "session-id"
    if session_id and (not session_file.exists() or session_file.read_text() != session_id):
        return False
    try:
        pid = int(pid_file.read_text())
        if pid <= 1:
            raise ValueError("Invalid registered backend PID")
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def bootstrap(release_root: Path, state_root: Path, revision: str) -> dict:
    prepare_state(state_root)
    lock_path = state_root / "startup.lock"
    if lock_path.is_symlink():
        raise ValueError("Controller lock must not be a symlink")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        secret = os.environ["CLOUD_CONTROL_SECRET"]
        current = _health(secret)
        if current and current.get("source_revision") == revision:
            return {"ready": True, "reused": True, "sourceRevision": revision}
        pid_file = state_root / "backend.pid"
        session_id = os.getenv("CLOUD_SESSION_ID", "")
        if not current and _registered_process_alive(pid_file, session_id):
            raise ValueError("The registered backend is still running but not ready; refusing a second process")
        if current:
            if current.get("active_cloud_job"):
                raise ValueError("Controller upgrade deferred: a browser job is active")
            # Only stop the PID registered by this bootstrap for the checked service.
            pid = int(pid_file.read_text())
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if _health(secret) is None:
                    break
                time.sleep(0.1)
            else:
                raise ValueError("Previous controller has not stopped; source remains unchanged")
        runtime_python = ensure_runtime(release_root, state_root)
        env = {**os.environ, "CLOUD_SOURCE_REVISION": revision,
               "DATABASE_PATH": str(state_root / "browser_automation.db"),
               "ARTIFACTS_ROOT": str(state_root / "artifacts"),
               "ARTIFACT_TRASH_ROOT": str(state_root / "artifacts/.trash"),
               "PYTHONPATH": str(release_root)}
        with (state_root / "backend.log").open("ab") as log:
            process = subprocess.Popen([str(runtime_python), "-m", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"],
                                       cwd=release_root, env=env, stdout=log, stderr=log, start_new_session=True)
        pid_file.write_text(str(process.pid))
        (state_root / "session-id").write_text(session_id)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError("Controller startup failed; inspect private controller diagnostics")
            if _health(secret):
                return {"ready": True, "reused": False, "sourceRevision": revision}
            time.sleep(0.25)
        process.terminate()
        raise ValueError("Controller readiness timed out")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    print(json.dumps(bootstrap(args.release_root, args.state_root, args.revision)))

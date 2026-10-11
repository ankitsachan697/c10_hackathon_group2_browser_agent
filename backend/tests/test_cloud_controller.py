import base64
import json
import time
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import Database
from backend.legacy_import import import_legacy_json
from backend.repositories import ProjectRepository


def cloud_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUD_MODE", "true")
    monkeypatch.setenv("CLOUD_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("CLOUD_CONTROL_SECRET", "synthetic-controller-secret-32-bytes")
    monkeypatch.setenv("CLOUD_MEDIA_SECRET", "synthetic-media-secret-of-32-bytes")
    monkeypatch.setenv("VERCEL_TEAM_ID", "team_vX4hl0qHhzt1aKFxd5wVJ7bU")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "prj_fixture")


def test_cloud_management_requires_auth(monkeypatch, tmp_path):
    from backend.cloud_policy import CloudPolicy
    from backend.cloud_auth import CloudAuthMiddleware
    cloud_env(monkeypatch, tmp_path)
    app = FastAPI()
    app.add_middleware(CloudAuthMiddleware, policy=CloudPolicy.from_env())
    app.get("/api/projects")(lambda: {"private": True})
    app.get("/api/demo-shop/demo_fixture")(lambda: "synthetic")
    app.get("/api/demo-shop/assets/shop.js")(lambda: "synthetic-js")
    with TestClient(app) as client:
        assert client.get("/api/projects").status_code == 401
        assert client.get("/api/projects", headers={"x-studio-control": "wrong"}).status_code == 401
        assert client.get("/api/projects", headers={"x-studio-control": "synthetic-controller-secret-32-bytes"}).status_code == 200
        assert client.get("/api/demo-shop/demo_fixture").status_code == 200
        assert client.get("/api/demo-shop/assets/shop.js").status_code == 200
        assert client.post("/api/demo-shop/demo_fixture").status_code == 401
        assert client.get("/api/demo-shop/../projects").status_code == 401


def test_initial_cloud_release_blocks_browser_and_agent_execution(monkeypatch, tmp_path):
    from backend.cloud_policy import CloudPolicy
    from backend.cloud_auth import CloudAuthMiddleware
    cloud_env(monkeypatch, tmp_path)
    app = FastAPI()
    app.add_middleware(CloudAuthMiddleware, policy=CloudPolicy.from_env())
    paths = ["/api/operations/generations", "/api/journeys/generate", "/api/journeys/jrn_fixture/run",
             "/api/projects/proj_fixture/run", "/api/runs/run_fixture/rerun", "/api/schedules/sch_fixture/run",
             "/api/discovery-and-generate", "/api/diagnose-and-repair", "/api/autonomous-run", "/api/execute-script"]
    for path in paths:
        app.post(path)(lambda: {"unsafe": "must not execute"})
    with TestClient(app) as client:
        for path in paths:
            response = client.post(path, headers={"x-studio-control": "synthetic-controller-secret-32-bytes"})
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "CLOUD_EXECUTION_PENDING"


def test_cloud_start_fails_closed_without_management_secret(monkeypatch, tmp_path):
    from backend.cloud_policy import CloudPolicy
    cloud_env(monkeypatch, tmp_path)
    monkeypatch.delenv("CLOUD_CONTROL_SECRET")
    with pytest.raises(ValueError, match="CLOUD_CONTROL_SECRET"):
        CloudPolicy.from_env()


def test_cloud_has_no_legacy_import(monkeypatch, tmp_path):
    cloud_env(monkeypatch, tmp_path)
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "legacy", "project": "Private history", "name": "Captured"}]))
    database = Database(tmp_path / "fresh.db")
    summary = import_legacy_json(database, cases, tmp_path / "runs.json")
    assert summary.projects == 0
    assert ProjectRepository(database).list() == []


def test_expired_sdk_credentials_fail_before_worker_creation(monkeypatch, tmp_path):
    from backend.cloud_policy import CloudPolicy
    cloud_env(monkeypatch, tmp_path)
    policy = CloudPolicy.from_env()
    policy.state_root.mkdir()
    claims = {"exp": int(time.time()) - 1, "owner_id": policy.team_id, "project_id": policy.project_id}
    token = "header." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".signature"
    (policy.state_root / "sdk-credentials.json").write_text(json.dumps({"token": token}))
    with pytest.raises(ValueError, match="expired"):
        policy.sdk_credentials()


def test_resuming_preserves_database_and_credential_key(tmp_path):
    from backend.cloud_lifecycle import prepare_state
    from backend.credential_vault import CredentialVault
    state = tmp_path / "state"
    prepare_state(state)
    database = Database(state / "browser_automation.db")
    database.initialize()
    project = ProjectRepository(database).create({"name": "Retained"})
    vault = CredentialVault.for_database(database.path)
    encrypted = vault.encrypt("synthetic", "synthetic-password")
    prepare_state(state)
    assert ProjectRepository(database).get(project["id"])["name"] == "Retained"
    resumed = CredentialVault.for_database(database.path)
    assert resumed.decrypt(encrypted)[1] == "synthetic-password"


def test_runtime_dependencies_are_reused_across_source_only_updates(tmp_path):
    from backend.cloud_lifecycle import ensure_runtime
    release = tmp_path / "release"
    (release / "backend").mkdir(parents=True)
    (release / "backend/requirements.txt").write_text("fastapi==0.135.0\n")
    state = tmp_path / "state"
    state.mkdir()
    commands = []
    def command(args, **kwargs):
        commands.append(args)
        runtime_python = state / "runtime-venv/bin/python"
        runtime_python.parent.mkdir(parents=True, exist_ok=True)
        runtime_python.touch()
    first = ensure_runtime(release, state, run_command=command)
    command_count = len(commands)
    second = ensure_runtime(release, state, run_command=command)
    assert first == second == state / "runtime-venv/bin/python"
    assert len(commands) == command_count
    (release / "backend/requirements.txt").write_text("fastapi==0.136.0\n")
    ensure_runtime(release, state, run_command=command)
    assert len(commands) > command_count


def test_bootstrap_refuses_second_process_when_registered_service_is_unready(monkeypatch, tmp_path):
    from backend import cloud_lifecycle
    state = tmp_path / "state"
    cloud_lifecycle.prepare_state(state)
    (state / "backend.pid").write_text(str(os.getpid()))
    monkeypatch.setenv("CLOUD_CONTROL_SECRET", "synthetic-controller-secret-32-bytes")
    monkeypatch.setattr(cloud_lifecycle, "_health", lambda secret: None)
    monkeypatch.setattr(cloud_lifecycle.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("duplicate backend process launched"))
    with pytest.raises(ValueError, match="registered"):
        cloud_lifecycle.bootstrap(tmp_path / "source", state, "fixture-revision")


def test_restored_pid_from_previous_vm_session_is_not_reused_or_killed(tmp_path):
    from backend.cloud_lifecycle import _registered_process_alive
    (tmp_path / "backend.pid").write_text(str(os.getpid()))
    (tmp_path / "session-id").write_text("old-synthetic-session")
    assert _registered_process_alive(tmp_path / "backend.pid", "new-synthetic-session") is False

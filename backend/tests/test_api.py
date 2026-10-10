from pathlib import Path
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import install_api
from backend.api.context import AppServices
from backend.artifact_store import ArtifactStore
from backend.database import Database
from backend.credential_vault import CredentialVault
from backend.orchestrator import RunOrchestrator
from backend.repositories import ArtifactRepository
from backend.scheduler import ScheduleService


class Runner:
    def __init__(self):
        self.calls = []

    async def execute_script(self, **kwargs):
        self.calls.append(kwargs)
        return {"passed": True, "status": "PASSED", "stderr": "", "stdout": "", "screenshots": [], "run_id": "runner", "run_dir": "/tmp"}


class Agents:
    generation_calls = 0

    def __init__(self):
        self.generation_calls = 0
        self.generation_arguments = []

    def generate_flow_script(self, **kwargs):
        self.generation_calls += 1
        self.generation_arguments.append(kwargs)
        return {"python_script": "print('generated')", "discovered_steps": ["open"]}

    def diagnose_and_repair(self, packet):
        return {}


class Adapter:
    def add_daily(self, *args): pass
    def remove(self, *args): pass
    def start(self): pass
    def shutdown(self): pass


@pytest.fixture
def api(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    agents = Agents()
    runner = Runner()
    vault = CredentialVault(base64.urlsafe_b64encode(b"a" * 32).decode())
    orchestrator = RunOrchestrator(database, runner, agents, 10, credential_vault=vault)
    scheduler = ScheduleService(database, orchestrator, Adapter())
    services = AppServices(
        database=database,
        orchestrator=orchestrator,
        scheduler=scheduler,
        artifacts=ArtifactStore(tmp_path / "artifacts", tmp_path / "trash", ArtifactRepository(database)),
        agents=agents,
        credential_vault=vault,
    )
    app = FastAPI()
    app.state.services = services
    install_api(app)
    return TestClient(app), services


def create_journey(client):
    project = client.post("/api/projects", json={"name": "Web"}).json()["data"]
    journey = client.post("/api/journeys", json={
        "project_id": project["id"], "name": "Login", "target_url": "https://app.invalid", "script": "print('saved')"
    }).json()["data"]
    return project, journey


def test_project_and_journey_crud_pagination_and_validation(api):
    client, _ = api
    assert client.post("/api/projects", json={}).status_code == 422
    project, journey = create_journey(client)
    response = client.get("/api/projects?limit=1&offset=0&search=Web").json()
    assert response["data"][0]["id"] == project["id"]
    assert response["meta"]["total"] == 1
    assert client.get(f"/api/journeys/{journey['id']}").json()["data"]["script"] == "print('saved')"


def test_run_now_and_reruns_never_generate(api):
    client, services = api
    project, journey = create_journey(client)
    direct = client.post(f"/api/journeys/{journey['id']}/run").json()["data"]
    assert direct["status"] == "PASSED"
    current = client.post(f"/api/runs/{direct['id']}/rerun", json={"mode": "current"}).json()["data"]
    snapshot = client.post(f"/api/runs/{direct['id']}/rerun", json={"mode": "snapshot"}).json()["data"]
    assert current["status"] == snapshot["status"] == "PASSED"
    assert client.post(f"/api/projects/{project['id']}/run").status_code == 200
    assert services.agents.generation_calls == 0


def test_run_detail_includes_attempts_and_stable_artifact_links(api):
    client, services = api
    _, journey = create_journey(client)
    run = client.post(f"/api/journeys/{journey['id']}/run").json()["data"]
    evidence = services.artifacts.root / run["id"] / "success.png"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_bytes(b"png")
    artifact = services.artifacts.repository.create({
        "run_id": run["id"], "kind": "screenshot", "storage_path": f"{run['id']}/success.png", "media_type": "image/png"
    })

    detail = client.get(f"/api/runs/{run['id']}").json()["data"]
    assert detail["attempts"][0]["attempt_number"] == 1
    assert detail["artifacts"][0]["id"] == artifact["id"]
    response = client.get(f"/api/artifacts/{artifact['id']}")
    assert response.status_code == 200
    assert response.content == b"png"


def test_generation_is_explicit(api):
    client, services = api
    project = client.post("/api/projects", json={"name": "Web"}).json()["data"]
    response = client.post("/api/journeys/generate", json={
        "project_id": project["id"], "name": "Generated", "target_url": "https://app.invalid", "objective": "Open page"
    })
    assert response.status_code == 201
    assert services.agents.generation_calls == 1


def test_generation_encrypts_credentials_and_only_sends_auth_metadata(api):
    client, services = api
    project = client.post("/api/projects", json={"name": "Web"}).json()["data"]

    response = client.post("/api/journeys/generate", json={
        "project_id": project["id"], "name": "Generated login",
        "target_url": "https://app.invalid", "objective": "Log in",
        "username": "student", "password": "Password123",
    })

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["has_credentials"] is True
    assert "username" not in payload and "password" not in payload and "credential_ciphertext" not in payload
    assert "student" not in payload["script"] and "Password123" not in payload["script"]
    assert services.agents.generation_arguments[-1]["credentials_meta"] == {"has_auth": True}
    with services.database.connect() as connection:
        stored = connection.execute("SELECT credential_ciphertext FROM journeys WHERE id=?", (payload["id"],)).fetchone()[0]
    assert stored and "student" not in stored and "Password123" not in stored


def test_saved_journey_credentials_are_injected_into_runner_only(api):
    client, services = api
    project = client.post("/api/projects", json={"name": "Web"}).json()["data"]
    journey = client.post("/api/journeys", json={
        "project_id": project["id"], "name": "Login", "target_url": "https://app.invalid",
        "script": "print('saved')", "username": "student", "password": "Password123",
    }).json()["data"]

    client.post(f"/api/journeys/{journey['id']}/run")

    call = services.orchestrator.runner.calls[-1]
    assert call["env_vars"] == {"AUTH_USERNAME": "student", "AUTH_PASSWORD": "Password123"}
    assert set(call["secrets"]) == {"student", "Password123"}


def test_credentials_can_be_replaced_without_returning_plaintext(api):
    client, services = api
    _, journey = create_journey(client)
    response = client.put(f"/api/journeys/{journey['id']}/credentials", json={"username": "replacement-user", "password": "replacement-secret"})
    assert response.status_code == 200
    assert response.json()["data"]["has_credentials"] is True
    rendered = response.text
    assert "replacement-user" not in rendered and "replacement-secret" not in rendered
    client.post(f"/api/journeys/{journey['id']}/regenerate")
    assert services.agents.generation_arguments[-1]["credentials_meta"] == {"has_auth": True}


def test_daily_schedule_crud_and_run_now(api):
    client, _ = api
    _, journey = create_journey(client)
    schedule = client.post("/api/schedules", json={
        "journey_id": journey["id"], "local_time": "09:30", "timezone": "Asia/Kolkata"
    }).json()["data"]
    run = client.post(f"/api/schedules/{schedule['id']}/run").json()["data"]
    assert client.delete(f"/api/schedules/{schedule['id']}").json()["data"]["deleted"] is True
    retained = client.get(f"/api/runs/{run['id']}")
    assert retained.status_code == 200
    assert retained.json()["data"]["schedule_id"] is None


def test_delete_preview_and_cascade(api):
    client, _ = api
    project, journey = create_journey(client)
    client.post(f"/api/journeys/{journey['id']}/run")
    preview = client.get(f"/api/projects/{project['id']}/deletion-impact").json()["data"]
    assert preview["journeys"] == 1
    assert preview["runs"] >= 1
    assert client.delete(f"/api/projects/{project['id']}").json()["data"]["deleted"] is True


def test_errors_are_structured_and_artifact_traversal_is_hidden(api):
    client, services = api
    missing = client.get("/api/projects/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/artifacts/../../etc/passwd").status_code in (404, 422)

import asyncio
import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import install_api
from backend.api.context import AppServices
from backend.credential_vault import CredentialVault
from backend.database import Database
from backend.n8n_client import AgentError
from backend.orchestrator import RunOrchestrator
from backend.repositories import JourneyRepository, ProjectRepository


class Agents:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def generate_flow_script(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"python_script": "print('generated')", "discovered_steps": ["open"], "agent_id": "discovery-1", "agent_source": "n8n"}


class Runner:
    def __init__(self):
        self.calls = []

    async def execute_script(self, **kwargs):
        self.calls.append(kwargs)
        return {"passed": True, "stdout": "", "stderr": "", "screenshots": []}


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "app.db")
    db.initialize()
    project = ProjectRepository(db).create({"name": "Web"})
    vault = CredentialVault(base64.urlsafe_b64encode(b"g" * 32).decode())
    agents, runner = Agents(), Runner()
    orchestrator = RunOrchestrator(db, runner, agents, 10, credential_vault=vault)
    request = {"project_id": project["id"], "name": "Login", "target_url": "https://example.test/login",
               "objective": "Log in", "username": "student", "password": "Password123", "browser_mode": "headless"}
    return db, agents, runner, orchestrator, vault, request


def coordinator_for(db, agents, orchestrator, vault):
    from backend.generation import GenerationCoordinator
    return GenerationCoordinator(db, agents, orchestrator, vault)


@pytest.mark.asyncio
async def test_generation_saves_script_and_runs_once_without_sending_credentials(setup):
    db, agents, runner, orchestrator, vault, request = setup
    coordinator = coordinator_for(db, agents, orchestrator, vault)
    operation = coordinator.submit(request, "request-1")
    with db.connect() as connection:
        stored = connection.execute("SELECT request_json FROM generation_operations WHERE id=?", (operation["id"],)).fetchone()[0]
    assert "Password123" not in stored and "student" not in stored

    await coordinator.execute(operation["id"])

    completed = coordinator.get(operation["id"])
    assert completed["status"] == "COMPLETED"
    assert completed["journey_id"] and completed["run_id"]
    assert JourneyRepository(db).get(completed["journey_id"])["script"] == "print('generated')"
    assert len(agents.calls) == len(runner.calls) == 1
    assert agents.calls[0]["credentials_meta"] == {"has_auth": True}
    assert "Password123" not in str(agents.calls)
    assert runner.calls[0]["env_vars"] == {"AUTH_USERNAME": "student", "AUTH_PASSWORD": "Password123"}


@pytest.mark.asyncio
async def test_duplicate_key_and_recovery_never_duplicate_first_run(setup):
    db, agents, runner, orchestrator, vault, request = setup
    coordinator = coordinator_for(db, agents, orchestrator, vault)
    first = coordinator.submit(request, "request-1")
    second = coordinator.submit(request, "request-1")
    assert second["id"] == first["id"]

    await coordinator.execute(first["id"])
    await coordinator.execute(first["id"])
    coordinator.recover()
    await asyncio.sleep(0)

    assert len(agents.calls) == len(runner.calls) == 1


@pytest.mark.asyncio
async def test_agent_failure_is_visible_without_saving_journey(setup):
    db, agents, _, orchestrator, vault, request = setup
    coordinator = coordinator_for(db, agents, orchestrator, vault)
    agents.error = AgentError("AGENT_NOT_CONFIGURED", "Discovery agent is unavailable")
    operation = coordinator.submit(request, "request-1")

    await coordinator.execute(operation["id"])

    failed = coordinator.get(operation["id"])
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == "AGENT_NOT_CONFIGURED"
    assert failed["journey_id"] is None
    assert JourneyRepository(db).list() == []


@pytest.mark.asyncio
async def test_unsafe_generated_script_is_rejected_before_journey_save(setup):
    db, agents, _, orchestrator, vault, request = setup
    coordinator = coordinator_for(db, agents, orchestrator, vault)
    agents.generate_flow_script = lambda **kwargs: {"python_script": "import subprocess\nsubprocess.run(['id'])", "discovered_steps": []}
    operation = coordinator.submit(request, "unsafe-request")

    await coordinator.execute(operation["id"])

    assert coordinator.get(operation["id"])["error_code"] == "AGENT_RESPONSE_INVALID"
    assert JourneyRepository(db).list() == []


def test_generation_endpoint_returns_operation_without_waiting_for_run(setup):
    db, agents, runner, orchestrator, vault, request = setup
    coordinator = coordinator_for(db, agents, orchestrator, vault)
    scheduled = []
    coordinator.schedule = lambda operation_id: scheduled.append(operation_id)
    app = FastAPI()
    app.state.services = AppServices(database=db, orchestrator=None, scheduler=None, artifacts=None,
                                     agents=agents, credential_vault=None, generation=coordinator)
    install_api(app)

    response = TestClient(app).post("/api/operations/generations", json=request, headers={"Idempotency-Key": "request-1"})

    assert response.status_code == 202
    operation = response.json()["data"]
    assert operation["status"] == "QUEUED"
    assert scheduled == [operation["id"]]
    assert not runner.calls


def test_generation_endpoint_can_schedule_on_request_event_loop(setup):
    db, agents, _, orchestrator, vault, request = setup
    coordinator = coordinator_for(db, agents, orchestrator, vault)
    app = FastAPI()
    app.state.services = AppServices(database=db, orchestrator=orchestrator, scheduler=None, artifacts=None,
                                     agents=agents, credential_vault=vault, generation=coordinator)
    install_api(app)

    response = TestClient(app).post("/api/operations/generations", json=request, headers={"Idempotency-Key": "request-2"})

    assert response.status_code == 202

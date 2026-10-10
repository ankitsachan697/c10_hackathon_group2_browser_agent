from pathlib import Path

import pytest

from backend.database import Database
from backend.models import RunStatus, TriggerSource
from backend.orchestrator import RunOrchestrator
from backend.repositories import JourneyRepository, ProjectRepository, RunRepository


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.scripts = []

    async def execute_script(self, **kwargs):
        self.scripts.append(kwargs["script_code"])
        return self.results.pop(0)


class FakeAgents:
    def __init__(self, repair=None, error=None):
        self.repair = repair
        self.error = error
        self.repair_calls = []
        self.generation_calls = 0

    def generate_flow_script(self, **kwargs):
        self.generation_calls += 1
        raise AssertionError("operational runs must not generate scripts")

    def diagnose_and_repair(self, packet):
        self.repair_calls.append(packet)
        if self.error:
            raise self.error
        return self.repair


def passing():
    return {"passed": True, "status": "PASSED", "stderr": "", "stdout": "", "screenshots": [], "run_id": "runner", "run_dir": "/tmp"}


def failing(message="Timeout waiting for locator('#submit')"):
    return {"passed": False, "status": "FAILED", "stderr": message, "stdout": "", "screenshots": ["failure.png"], "run_id": "runner", "run_dir": "/tmp", "dom_snapshot": "<button>Submit</button>"}


@pytest.fixture
def domain(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    project = ProjectRepository(database).create({"name": "Web"})
    journey = JourneyRepository(database).create({"project_id": project["id"], "name": "Flow", "target_url": "https://app.invalid", "script": "print('saved')"})
    return database, project, journey


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", list(TriggerSource))
async def test_all_operational_triggers_execute_saved_script_without_generation(domain, trigger):
    database, _, journey = domain
    runner, agents = FakeRunner([passing()]), FakeAgents()
    orchestrator = RunOrchestrator(database, runner, agents, timeout_seconds=30)

    run = await orchestrator.run_journey(journey["id"], trigger)

    assert run["status"] == RunStatus.PASSED
    assert runner.scripts == ["print('saved')"]
    assert agents.generation_calls == 0
    assert agents.repair_calls == []


@pytest.mark.asyncio
async def test_project_run_executes_each_saved_journey(domain):
    database, project, _ = domain
    JourneyRepository(database).create({"project_id": project["id"], "name": "Second", "target_url": "https://app.invalid/two", "script": "print('second')"})
    runner, agents = FakeRunner([passing(), passing()]), FakeAgents()

    runs = await RunOrchestrator(database, runner, agents, 30).run_project(project["id"], TriggerSource.PROJECT)

    assert len(runs) == 2
    assert set(runner.scripts) == {"print('saved')", "print('second')"}
    assert agents.generation_calls == 0


@pytest.mark.asyncio
async def test_eligible_failure_repairs_once_and_records_healed_pass(domain):
    database, _, journey = domain
    runner = FakeRunner([failing(), passing()])
    agents = FakeAgents({"repaired_script": "print('healed')", "root_cause": "selector", "recommended_fix": "use role"})

    run = await RunOrchestrator(database, runner, agents, 30).run_journey(journey["id"], TriggerSource.ON_DEMAND, secrets=["secret"])

    assert run["status"] == RunStatus.PASSED_AFTER_REPAIR
    assert run["attempt_count"] == 2
    assert runner.scripts == ["print('saved')", "print('healed')"]
    assert len(agents.repair_calls) == 1


@pytest.mark.asyncio
async def test_second_failure_needs_attention_and_never_retries_again(domain):
    database, _, journey = domain
    runner = FakeRunner([failing(), failing("Timeout again")])
    agents = FakeAgents({"repaired_script": "print('healed')", "root_cause": "selector", "recommended_fix": "use role"})

    run = await RunOrchestrator(database, runner, agents, 30).run_journey(journey["id"], TriggerSource.SCHEDULED)

    assert run["status"] == RunStatus.NEEDS_ATTENTION
    assert run["attempt_count"] == 2
    assert len(agents.repair_calls) == 1


@pytest.mark.asyncio
async def test_ineligible_or_broken_agent_response_needs_attention_without_retry(domain):
    database, _, journey = domain
    for agents, result in (
        (FakeAgents({"repaired_script": "ignored"}), failing("401 Unauthorized invalid credentials")),
        (FakeAgents({"unexpected": True}), failing()),
        (FakeAgents(error=TimeoutError("n8n unavailable")), failing()),
    ):
        runner = FakeRunner([result])
        run = await RunOrchestrator(database, runner, agents, 30).run_journey(journey["id"], TriggerSource.ON_DEMAND)
        assert run["status"] == RunStatus.NEEDS_ATTENTION
        assert len(runner.scripts) == 1


@pytest.mark.asyncio
async def test_snapshot_rerun_uses_historical_script(domain):
    database, _, journey = domain
    historic = RunRepository(database).create({"journey_id": journey["id"], "status": "FAILED", "script_snapshot": "print('historic')", "script_version": 1})
    JourneyRepository(database).update(journey["id"], {"script": "print('current')"})
    runner, agents = FakeRunner([passing()]), FakeAgents()

    await RunOrchestrator(database, runner, agents, 30).run_journey(journey["id"], TriggerSource.RERUN_SNAPSHOT, script_version=historic["id"])

    assert runner.scripts == ["print('historic')"]

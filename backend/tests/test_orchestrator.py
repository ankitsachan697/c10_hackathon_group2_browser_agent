from pathlib import Path
import base64

import pytest

from backend.database import Database
from backend.event_store import EventStore
from backend.credential_vault import CredentialVault
from backend.models import RunStatus, TriggerSource
from backend.orchestrator import RunOrchestrator
from backend.repositories import JourneyRepository, ProjectRepository, RunRepository


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.scripts = []
        self.calls = []

    async def execute_script(self, **kwargs):
        self.calls.append(kwargs)
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
async def test_saved_run_persists_real_actions_and_headed_choice_without_discovery(domain):
    database, _, journey = domain

    class EventRunner(FakeRunner):
        async def execute_script(self, **kwargs):
            self.calls.append(kwargs)
            kwargs["on_action"]({"action": "fill", "phase": "started"})
            kwargs["on_action"]({"action": "fill", "phase": "finished"})
            kwargs["on_log"]({"level": "INFO", "message": "password=Password123"})
            return passing()

    runner, agents = EventRunner([passing()]), FakeAgents()
    run = await RunOrchestrator(database, runner, agents, 30).run_journey(
        journey["id"], TriggerSource.ON_DEMAND, secrets=["Password123"], headed=True
    )
    events = EventStore(database).list_after("run", run["id"], 0)

    assert runner.calls[0]["headed"] is True
    assert [event["kind"] for event in events].count("action.started") == 1
    assert not any(event["kind"].startswith("generation") for event in events)
    assert "Password123" not in str(events)


@pytest.mark.asyncio
async def test_visual_agent_failure_keeps_functional_pass(domain):
    database, _, journey = domain
    class FailedVisual:
        def review(self, *args, **kwargs):
            return {"status": "MATCH", "agent_status": "ERROR", "agent_error_code": "AGENT_UNAVAILABLE"}

    run = await RunOrchestrator(database, FakeRunner([passing()]), FakeAgents(), 30,
                                visual_review=FailedVisual()).run_journey(journey["id"], TriggerSource.ON_DEMAND)
    events = EventStore(database).list_after("run", run["id"], 0)
    assert run["status"] == RunStatus.PASSED
    assert run["visual_outcome"] == "MATCH"
    assert any(event["kind"] == "visual.finished" and event["payload"]["agent_status"] == "ERROR" for event in events)
    with database.connect() as connection:
        visual = connection.execute("SELECT payload_json FROM visual_reviews WHERE run_id=?", (run["id"],)).fetchone()
    assert visual is not None


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
    with database.connect() as connection:
        attempts = connection.execute(
            "SELECT attempt_number, status FROM run_attempts WHERE run_id = ? ORDER BY attempt_number", (run["id"],)
        ).fetchall()
    assert [(row[0], row[1]) for row in attempts] == [(1, "FAILED"), (2, "PASSED")]
    assert run["started_at"] is not None
    assert run["finished_at"] is not None
    events = EventStore(database).list_after("run", run["id"], 0)
    kinds = [event["kind"] for event in events]
    assert kinds.index("run.attempt_finished") < kinds.index("repair.started") < kinds.index("repair.finished") < kinds.index("run.retry_started")
    assert [(event["payload"]["attempt"], event["payload"]["passed"]) for event in events if event["kind"] == "run.attempt_finished"] == [(1, False), (2, True)]
    assert runner.calls[1]["on_action"] is not None
    with database.connect() as connection:
        invocations = [dict(row) for row in connection.execute("SELECT * FROM agent_invocations WHERE run_id=?", (run["id"],))]
    assert len(invocations) == 1
    assert invocations[0]["purpose"] == "repair" and invocations[0]["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_second_failure_needs_attention_and_never_retries_again(domain):
    database, _, journey = domain
    runner = FakeRunner([failing(), failing("Timeout again")])
    agents = FakeAgents({"repaired_script": "print('healed')", "root_cause": "selector", "recommended_fix": "use role"})

    run = await RunOrchestrator(database, runner, agents, 30).run_journey(journey["id"], TriggerSource.SCHEDULED)

    assert run["status"] == RunStatus.NEEDS_ATTENTION
    assert run["attempt_count"] == 2
    assert len(agents.repair_calls) == 1
    events = EventStore(database).list_after("run", run["id"], 0)
    assert len([event for event in events if event["kind"] == "run.retry_started"]) == 1


@pytest.mark.asyncio
async def test_repair_failure_is_visible_and_does_not_retry(domain):
    database, _, journey = domain
    runner = FakeRunner([failing()])
    run = await RunOrchestrator(database, runner, FakeAgents(error=TimeoutError("n8n unavailable")), 30).run_journey(journey["id"], TriggerSource.ON_DEMAND)
    events = EventStore(database).list_after("run", run["id"], 0)
    assert run["status"] == RunStatus.NEEDS_ATTENTION
    assert len(runner.calls) == 1
    assert any(event["kind"] == "repair.failed" for event in events)
    with database.connect() as connection:
        invocation = connection.execute("SELECT status,error_code FROM agent_invocations WHERE run_id=?", (run["id"],)).fetchone()
    assert tuple(invocation) == ("FAILED", "TimeoutError")


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


@pytest.mark.asyncio
async def test_unexpected_runner_error_finalizes_run_for_manual_attention(domain):
    database, _, journey = domain

    class BrokenRunner:
        async def execute_script(self, **kwargs):
            raise RuntimeError("worker crashed")

    run = await RunOrchestrator(database, BrokenRunner(), FakeAgents(), 30).run_journey(
        journey["id"], TriggerSource.ON_DEMAND
    )

    assert run["status"] == RunStatus.NEEDS_ATTENTION
    assert run["finished_at"] is not None
    assert "RuntimeError" in run["final_decision"]


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", [
    TriggerSource.ON_DEMAND, TriggerSource.SCHEDULED, TriggerSource.PROJECT,
    TriggerSource.RERUN_CURRENT, TriggerSource.RERUN_SNAPSHOT,
])
async def test_every_trigger_injects_decrypted_credentials(domain, trigger):
    database, _, journey = domain
    vault = CredentialVault(base64.urlsafe_b64encode(b"b" * 32).decode())
    JourneyRepository(database).set_credentials(journey["id"], vault.encrypt("student", "Password123"))
    runner = FakeRunner([passing()])
    orchestrator = RunOrchestrator(database, runner, FakeAgents(), 30, credential_vault=vault)
    historic_id = None
    if trigger == TriggerSource.RERUN_SNAPSHOT:
        historic_id = RunRepository(database).create({
            "journey_id": journey["id"], "status": "FAILED", "script_snapshot": "print('historic')", "script_version": 1
        })["id"]

    await orchestrator.run_journey(journey["id"], trigger, script_version=historic_id)

    assert runner.calls[0]["env_vars"] == {"AUTH_USERNAME": "student", "AUTH_PASSWORD": "Password123"}
    assert set(runner.calls[0]["secrets"]) == {"student", "Password123"}


@pytest.mark.asyncio
async def test_repair_retry_reuses_credentials_and_redacts_failure_packet(domain):
    database, _, journey = domain
    vault = CredentialVault(base64.urlsafe_b64encode(b"c" * 32).decode())
    JourneyRepository(database).set_credentials(journey["id"], vault.encrypt("student", "Password123"))
    runner = FakeRunner([failing("Timeout Password123 student"), passing()])
    agents = FakeAgents({"repaired_script": "print('healed')"})

    await RunOrchestrator(database, runner, agents, 30, credential_vault=vault).run_journey(
        journey["id"], TriggerSource.ON_DEMAND
    )

    assert len(runner.calls) == 2
    assert runner.calls[1]["env_vars"]["AUTH_PASSWORD"] == "Password123"
    assert "Password123" not in agents.repair_calls[0].traceback
    assert "student" not in agents.repair_calls[0].traceback


@pytest.mark.asyncio
async def test_run_registers_complete_evidence_without_credentials(domain, tmp_path):
    database, _, journey = domain
    vault = CredentialVault(base64.urlsafe_b64encode(b"d" * 32).decode())
    JourneyRepository(database).set_credentials(journey["id"], vault.encrypt("student", "Password123"))

    class EvidenceRunner(FakeRunner):
        artifacts_dir = str(tmp_path)

        async def execute_script(self, **kwargs):
            run_dir = tmp_path / kwargs["execution_id"]
            run_dir.mkdir(parents=True)
            (run_dir / "step_1_landing.png").write_bytes(b"png")
            (run_dir / "session_video.webm").write_bytes(b"video" * 200)
            (run_dir / "execution.log").write_text("account=student password=Password123 card=4111 1111 1111 1111 cvv=123")
            return {**passing(), "run_dir": str(run_dir), "stdout": "student Password123 card=4111 1111 1111 1111 cvv=123"}

    run = await RunOrchestrator(database, EvidenceRunner([passing()]), FakeAgents(), 30, credential_vault=vault).run_journey(
        journey["id"], TriggerSource.ON_DEMAND
    )
    detail = RunRepository(database).get(run["id"])
    with database.connect() as connection:
        attempts = [dict(row) for row in connection.execute("SELECT * FROM run_attempts WHERE run_id=?", (run["id"],))]
        artifacts = [dict(row) for row in connection.execute("SELECT * FROM artifacts WHERE run_id=?", (run["id"],))]

    assert detail["script_snapshot"] == "print('saved')"
    assert {item["kind"] for item in artifacts} == {"screenshot", "video", "log"}
    assert len(attempts) == 1
    assert "student" not in str(attempts) and "Password123" not in str(attempts)
    assert "4111" not in str(attempts) and "cvv=123" not in str(attempts)
    assert "student" not in (tmp_path / run["id"] / "attempt-1" / "execution.log").read_text()
    assert "Password123" not in (tmp_path / run["id"] / "attempt-1" / "execution.log").read_text()
    assert "4111" not in (tmp_path / run["id"] / "attempt-1" / "execution.log").read_text()


@pytest.mark.asyncio
async def test_missing_vault_creates_auditable_needs_attention_run(domain):
    database, _, journey = domain
    vault = CredentialVault(base64.urlsafe_b64encode(b"e" * 32).decode())
    JourneyRepository(database).set_credentials(journey["id"], vault.encrypt("student", "Password123"))

    run = await RunOrchestrator(database, FakeRunner([]), FakeAgents(), 30, credential_vault=None).run_journey(
        journey["id"], TriggerSource.SCHEDULED
    )

    assert run["status"] == RunStatus.NEEDS_ATTENTION
    assert run["final_decision"] == "Credential vault unavailable"


@pytest.mark.asyncio
async def test_artifact_symlinks_are_removed_without_following_them(domain, tmp_path):
    database, _, journey = domain
    outside = tmp_path / "outside.txt"
    outside.write_text("must remain unchanged")

    class SymlinkRunner(FakeRunner):
        artifacts_dir = str(tmp_path / "artifacts")
        async def execute_script(self, **kwargs):
            run_dir = Path(self.artifacts_dir) / kwargs["execution_id"]
            run_dir.mkdir(parents=True)
            (run_dir / "execution.log").symlink_to(outside)
            return {**passing(), "run_dir": str(run_dir)}

    await RunOrchestrator(database, SymlinkRunner([passing()]), FakeAgents(), 30).run_journey(
        journey["id"], TriggerSource.ON_DEMAND
    )

    assert outside.read_text() == "must remain unchanged"
    assert not list((tmp_path / "artifacts").rglob("execution.log"))

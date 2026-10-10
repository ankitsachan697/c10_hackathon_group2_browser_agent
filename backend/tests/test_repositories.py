from pathlib import Path

import pytest

from backend.database import Database
from backend.repositories import (
    ArtifactRepository,
    EnvironmentRepository,
    JourneyRepository,
    ProjectRepository,
    RunRepository,
    ScheduleRepository,
)


@pytest.fixture
def store(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    return database


def test_domain_crud_and_relationships(store):
    environments = EnvironmentRepository(store)
    projects = ProjectRepository(store)
    journeys = JourneyRepository(store)
    schedules = ScheduleRepository(store)
    runs = RunRepository(store)
    artifacts = ArtifactRepository(store)

    environment = environments.create({"name": "QA", "base_url": "https://qa.invalid"})
    project = projects.create({"name": "Checkout", "environment_id": environment["id"]})
    journey = journeys.create({
        "project_id": project["id"],
        "name": "Guest purchase",
        "objective": "Complete checkout",
        "target_url": "https://qa.invalid/cart",
        "script": "print('v1')",
    })
    schedule = schedules.create({
        "journey_id": journey["id"],
        "local_time": "09:30",
        "timezone": "Asia/Kolkata",
    })
    run = runs.create({
        "journey_id": journey["id"],
        "schedule_id": schedule["id"],
        "trigger_source": "SCHEDULED",
        "status": "QUEUED",
        "script_snapshot": journey["script"],
        "script_version": journey["script_version"],
    })
    artifact = artifacts.create({"run_id": run["id"], "kind": "screenshot", "storage_path": "run/a.png"})

    assert projects.get(project["id"])["name"] == "Checkout"
    assert journeys.get(journey["id"])["script_version"] == 1
    assert schedules.get(schedule["id"])["journey_id"] == journey["id"]
    assert runs.get(run["id"])["script_snapshot"] == "print('v1')"
    assert artifacts.get(artifact["id"])["run_id"] == run["id"]


def test_run_script_snapshot_is_immutable(store):
    projects = ProjectRepository(store)
    journeys = JourneyRepository(store)
    runs = RunRepository(store)
    project = projects.create({"name": "Auth"})
    journey = journeys.create({
        "project_id": project["id"], "name": "Login", "target_url": "https://app.invalid", "script": "v1"
    })
    run = runs.create({"journey_id": journey["id"], "status": "QUEUED", "script_snapshot": "v1", "script_version": 1})

    journeys.update(journey["id"], {"script": "v2"})

    assert runs.get(run["id"])["script_snapshot"] == "v1"
    assert journeys.get(journey["id"])["script_version"] == 2


def test_project_delete_cascades_in_one_transaction(store):
    projects = ProjectRepository(store)
    journeys = JourneyRepository(store)
    schedules = ScheduleRepository(store)
    runs = RunRepository(store)
    project = projects.create({"name": "Disposable"})
    journey = journeys.create({"project_id": project["id"], "name": "Flow", "target_url": "https://x.invalid", "script": "pass"})
    schedule = schedules.create({"journey_id": journey["id"], "local_time": "12:00", "timezone": "UTC"})
    run = runs.create({"journey_id": journey["id"], "schedule_id": schedule["id"], "status": "QUEUED", "script_snapshot": "pass", "script_version": 1})

    assert projects.delete(project["id"]) is True
    assert projects.get(project["id"]) is None
    assert journeys.get(journey["id"]) is None
    assert schedules.get(schedule["id"]) is None
    assert runs.get(run["id"]) is None


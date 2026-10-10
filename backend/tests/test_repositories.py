from pathlib import Path
import sqlite3

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


def test_existing_database_adds_journey_credential_storage_in_place(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta VALUES ('schema_version', '1');
            CREATE TABLE journeys (
              id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
              objective TEXT NOT NULL DEFAULT '', target_url TEXT NOT NULL,
              script TEXT NOT NULL, script_version INTEGER NOT NULL DEFAULT 1,
              active INTEGER NOT NULL DEFAULT 1, browser_json TEXT NOT NULL DEFAULT '{}',
              visual_threshold REAL, baseline_state TEXT, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
        """)

    database = Database(path)
    database.initialize()
    database.initialize()

    with database.connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(journeys)")}
        version = connection.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
    assert "credential_ciphertext" in columns
    assert version == "2"


def test_journey_repository_keeps_ciphertext_private(store):
    projects = ProjectRepository(store)
    journeys = JourneyRepository(store)
    project = projects.create({"name": "Authentication"})
    journey = journeys.create({
        "project_id": project["id"], "name": "Login", "target_url": "https://app.invalid", "script": "pass"
    })

    updated = journeys.set_credentials(journey["id"], "opaque-ciphertext")

    assert updated["has_credentials"] is True
    assert "credential_ciphertext" not in updated
    assert "credential_ciphertext" not in journeys.get(journey["id"])
    assert "credential_ciphertext" not in journeys.list()[0]
    assert journeys.get_with_credentials(journey["id"])["credential_ciphertext"] == "opaque-ciphertext"

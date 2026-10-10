import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import install_api
from backend.api.context import AppServices
from backend.database import Database
from backend.repositories import JourneyRepository, ProjectRepository, RunRepository


def event_store(database):
    from backend.event_store import EventStore
    return EventStore(database)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "history.db")
    database.initialize()
    return database


def test_events_are_ordered_redacted_and_reconnectable(db):
    events = event_store(db)
    first = events.append("run", "run-1", "playwright", "action.started", {"action": "fill", "detail": "password=private-value"})
    second = events.append("run", "run-1", "playwright", "action.finished", {"detail": "card 4111 1111 1111 1111"})
    events.append("run", "other-run", "playwright", "action.finished", {"detail": "other"})

    assert first["seq"] < second["seq"]
    assert events.list_after("run", "run-1", first["seq"]) == [second]
    assert "private-value" not in json.dumps(events.list_after("run", "run-1", 0))
    assert "4111" not in json.dumps(events.list_after("run", "run-1", 0))


def test_feed_is_limited_and_rejects_oversized_payload(db):
    events = event_store(db)
    for number in range(205):
        events.append("operation", "op-1", "system", "tick", {"number": number})

    page = events.list_after("operation", "op-1", 0, limit=1000)
    assert len(page) == 200
    assert page[0]["payload"]["number"] == 0
    assert len(events.list_after("operation", "op-1", page[-1]["seq"])) == 5
    with pytest.raises(ValueError, match="4 KiB"):
        events.append("operation", "op-1", "system", "tick", {"text": "x" * 5000})


def test_event_redacts_registered_secret_before_json_escaping(db):
    secret = 'p@ss"word'
    event = event_store(db).append("run", "run-1", "playwright", "output", {"text": f"value {secret}"}, secrets=[secret])

    assert secret not in event["payload"]["text"]
    assert secret not in json.dumps(event)


def test_migration_preserves_existing_journey_and_run(tmp_path):
    database = Database(tmp_path / "existing.db")
    database.initialize()
    project = ProjectRepository(database).create({"name": "Existing"})
    journey = JourneyRepository(database).create({"project_id": project["id"], "name": "Login", "target_url": "https://example.test"})
    run = RunRepository(database).create({"journey_id": journey["id"], "project_id": project["id"], "status": "QUEUED"})

    database.initialize()

    assert JourneyRepository(database).get(journey["id"])["name"] == "Login"
    assert RunRepository(database).get(run["id"])["status"] == "QUEUED"
    assert event_store(database).append("run", run["id"], "system", "queued", {})["seq"] > 0


def test_event_routes_return_only_the_requested_scope(db):
    event_store(db).append("run", "run-1", "system", "queued", {})
    event = event_store(db).append("operation", "op-1", "agent", "generation.started", {})
    with db.transaction() as connection:
        connection.execute("INSERT INTO generation_operations(id,idempotency_key,status,request_json,created_at,updated_at) VALUES (?,?,?,?,?,?)", ("op-1", "request-1", "RUNNING", "{}", "now", "now"))
    app = FastAPI()
    app.state.services = AppServices(database=db, orchestrator=None, scheduler=None, artifacts=None, agents=None)
    install_api(app)
    client = TestClient(app)

    operation = client.get("/api/operations/op-1").json()["data"]
    assert operation["status"] == "RUNNING"
    assert client.get("/api/operations/op-1/events?after_seq=0").json()["data"] == [event]
    assert client.get("/api/runs/run-1/events?after_seq=0").json()["data"][0]["kind"] == "queued"

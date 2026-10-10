from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import install_api
from backend.api.context import AppServices
from backend.companion_registry import CompanionRegistry, CompanionError
from backend.database import Database


@pytest.fixture
def registry(tmp_path):
    database = Database(tmp_path / "registry.db")
    database.initialize()
    return CompanionRegistry(database, "operator-secret")


def test_pair_code_is_one_time_and_device_credential_is_hashed(registry):
    pair = registry.issue_pair_code("default")
    device = registry.exchange(pair["code"], "Demo laptop")
    assert device["id"]
    assert device["credential"]
    with registry.database.connect() as connection:
        stored = connection.execute("SELECT credential_hash FROM companions WHERE id=?", (device["id"],)).fetchone()[0]
    assert device["credential"] not in stored
    with pytest.raises(CompanionError):
        registry.exchange(pair["code"], "Second laptop")


def test_expired_pair_code_and_revoked_device_are_rejected(registry):
    pair = registry.issue_pair_code("default")
    with registry.database.transaction() as connection:
        connection.execute("UPDATE companion_pair_codes SET expires_at=?", ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
    with pytest.raises(CompanionError):
        registry.exchange(pair["code"], "Too late")
    fresh = registry.issue_pair_code("default")
    device = registry.exchange(fresh["code"], "Demo laptop")
    registry.heartbeat(device["id"], device["credential"])
    assert registry.list_online()[0]["id"] == device["id"]
    registry.revoke(device["id"])
    assert registry.list_online() == []
    with pytest.raises(CompanionError):
        registry.heartbeat(device["id"], device["credential"])


def test_pairing_requires_operator_secret_and_public_status_excludes_credentials(tmp_path):
    database = Database(tmp_path / "registry.db")
    database.initialize()
    with pytest.raises(CompanionError):
        CompanionRegistry(database, None).issue_pair_code("default")
    registry = CompanionRegistry(database, "operator-secret")
    app = FastAPI()
    app.state.services = AppServices(database=database, orchestrator=None, scheduler=None, artifacts=None,
                                     agents=None, companions=registry)
    install_api(app)
    client = TestClient(app)
    assert client.post("/api/companions/pair-codes").status_code == 403
    assert client.post("/api/companions/pair-codes", headers={"X-Companion-Admin-Token": "wrong"}).status_code == 403
    pair = client.post("/api/companions/pair-codes", headers={"X-Companion-Admin-Token": "operator-secret"}).json()["data"]
    device = client.post("/api/companions/exchange", json={"code": pair["code"], "device_name": "Laptop"}).json()["data"]
    registry.heartbeat(device["id"], device["credential"])
    public = client.get("/api/companions").json()["data"]
    assert public == [{"id": device["id"], "name": "Laptop", "online": True}]
    assert device["credential"] not in str(public)

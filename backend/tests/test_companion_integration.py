from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import install_api
from backend.api.context import AppServices
from backend.cdp_relay import CdpRelay
from backend.companion_registry import CompanionRegistry
from backend.database import Database


def test_pair_approve_and_bridge_cdp_frames_without_control_secrets(tmp_path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    registry = CompanionRegistry(database, "operator-secret")
    relay = CdpRelay()
    app = FastAPI()
    app.state.services = AppServices(database=database, orchestrator=None, scheduler=None, artifacts=None,
                                     agents=None, companions=registry, relay=relay)
    install_api(app)

    with TestClient(app) as client:
        pair = client.post("/api/companions/pair-codes", headers={"X-Companion-Admin-Token": "operator-secret"}).json()["data"]
        device = client.post("/api/companions/exchange", json={"code": pair["code"], "device_name": "Demo laptop"}).json()["data"]
        client.post("/api/companions/heartbeat", json={"device_id": device["id"]},
                    headers={"Authorization": f"Bearer {device['credential']}"})
        session = relay.create_session(device["id"], "run-1")
        offers = client.get(f"/api/companions/{device['id']}/sessions",
                            headers={"Authorization": f"Bearer {device['credential']}"}).json()["data"]
        assert offers == [{"type": "session_offer", "session_id": session.id, "run_id": "run-1"}]
        assert device["credential"] not in str(offers)

        with client.websocket_connect(f"/api/companions/relay/{session.id}/companion", headers={
            "X-Companion-Device-Id": device["id"], "Authorization": f"Bearer {device['credential']}",
        }) as companion:
            with client.websocket_connect(f"/api/companions/relay/{session.id}/runner", headers={
                "Authorization": f"Bearer {session.runner_secret}",
            }) as runner:
                runner.send_text('{"id":1,"method":"Page.enable"}')
                assert companion.receive_text() == '{"id":1,"method":"Page.enable"}'
                companion.send_text('{"id":1,"result":{}}')
                assert runner.receive_text() == '{"id":1,"result":{}}'

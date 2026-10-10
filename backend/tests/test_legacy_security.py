from fastapi.testclient import TestClient

from backend import server


def test_legacy_raw_execution_routes_are_retired():
    client = TestClient(server.app)

    assert client.post("/api/execute", json={"script": "print('unsafe')"}).status_code == 410
    assert client.post("/api/execute-script", json={"script": "print('unsafe')"}).status_code == 410
    assert client.post("/api/test-cases/anything/run").status_code == 410


def test_legacy_artifact_route_cannot_read_paths():
    client = TestClient(server.app)

    assert client.get("/api/legacy/artifacts/%2E%2E/backend/config.py").status_code == 410
    assert client.get("/api/legacy/artifacts/%2Fetc%2Fpasswd").status_code == 410

import json
import pytest
from backend.tests.test_api import api, create_journey
from backend.repositories import RunRepository


def test_metrics_are_real_and_active_runs_do_not_reduce_pass_rate(api):
    client, svc = api
    project, journey = create_journey(client)
    repo = RunRepository(svc.database)
    for status in ['PASSED', 'PASSED_AFTER_REPAIR', 'NEEDS_ATTENTION', 'RUNNING', 'QUEUED']:
        repo.create({'journey_id': journey['id'], 'project_id': project['id'], 'status': status})
    result = client.get('/api/overview').json()['data']
    assert result['total_runs'] == 5 and result['completed_runs'] == 3
    assert result['pass_rate'] == 66.7 and result['needs_attention'] == 1 and result['repaired_runs'] == 1
    assert result['active_runs'] == 2 and result['projects'] == 1 and result['journeys'] == 1
    assert result['next_schedule'] is None


def test_run_delete_clears_audit_references_and_updates_metrics(api):
    client, svc = api
    project, journey = create_journey(client)
    run = RunRepository(svc.database).create({'journey_id': journey['id'], 'project_id': project['id'], 'status': 'PASSED'})
    with svc.database.connect() as db:
        db.execute("INSERT INTO activity_events(scope_type,scope_id,source,kind,payload_json,created_at) VALUES ('run',?,'system','test','{}','now')", (run['id'],))
        db.execute("INSERT INTO agent_invocations(id,run_id,agent_id,purpose,status,created_at) VALUES ('inv',?,'repair','repair','SUCCEEDED','now')", (run['id'],))
        db.execute("INSERT INTO generation_operations(id,idempotency_key,status,request_json,run_id,created_at,updated_at) VALUES ('gen','key','COMPLETED','{}',?,'now','now')", (run['id'],))
    assert client.delete(f"/api/runs/{run['id']}").status_code == 200
    assert client.get('/api/overview').json()['data']['total_runs'] == 0
    assert client.get(f"/api/runs/{run['id']}").status_code == 404
    with svc.database.connect() as db:
        assert db.execute('SELECT count(*) FROM activity_events WHERE scope_id=?', (run['id'],)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM agent_invocations WHERE run_id=?', (run['id'],)).fetchone()[0] == 0
        assert db.execute("SELECT run_id FROM generation_operations WHERE id='gen'").fetchone()[0] is None


@pytest.mark.parametrize('status', ['QUEUED', 'RUNNING', 'DIAGNOSING', 'REPAIRING', 'RETRYING'])
def test_active_run_cannot_be_deleted(api, status):
    client, svc = api
    run = RunRepository(svc.database).create({'status': status})
    assert client.delete(f"/api/runs/{run['id']}").status_code == 409
    assert client.get(f"/api/runs/{run['id']}").status_code == 200
    assert client.delete('/api/runs/missing').status_code == 404


def test_background_rerun_returns_live_run_id_before_worker_finishes(api):
    import asyncio
    import time
    client, svc = api
    project, journey = create_journey(client)
    original = RunRepository(svc.database).create({'journey_id': journey['id'], 'project_id': project['id'], 'status': 'PASSED'})
    class SlowRunner:
        async def execute_script(self, **kwargs):
            await asyncio.sleep(.2)
            return {'passed': True, 'screenshots': [], 'stderr': '', 'stdout': ''}
    svc.orchestrator.runner = SlowRunner()
    with client:
        response = client.post(f"/api/runs/{original['id']}/rerun", json={'mode': 'snapshot', 'background': True})
        assert response.status_code == 202
        run = response.json()['data']
        assert run['status'] == 'QUEUED' and run['id'] != original['id']
        for _ in range(100):
            result = client.get(f"/api/runs/{run['id']}").json()['data']
            if result['status'] == 'PASSED':
                break
            time.sleep(.02)
        assert result['status'] == 'PASSED'

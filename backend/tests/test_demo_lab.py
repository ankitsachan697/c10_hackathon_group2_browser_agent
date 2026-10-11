import pytest

from backend.tests.test_api import api
from backend.runner import PlaywrightRunner


def test_scenario_isolated_partial_updates_and_html_available(api):
    client, _ = api
    first = client.post('/api/demo-lab/scenarios', json={}).json()['data']
    second = client.post('/api/demo-lab/scenarios', json={}).json()['data']
    changed = client.patch(f"/api/demo-lab/scenarios/{first['id']}", json={'locator_revision': 1, 'visual_variant': True}).json()['data']
    changed = client.patch(f"/api/demo-lab/scenarios/{first['id']}", json={'checkout_failure': True}).json()['data']
    assert changed['locator_revision'] == 1 and changed['visual_variant'] and changed['checkout_failure']
    assert client.get('/api/demo-lab/scenarios').json()['data'][0]['id'] == second['id']
    assert second['locator_revision'] == 0 and not second['visual_variant']
    response = client.get(f"/api/demo-shop/{first['id']}")
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/html')
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/demo-shop/assets/shop.js').status_code == 200
    assert client.get('/api/demo-shop/assets/../../server.py').status_code == 404


def test_scenario_invalid_revision_and_unknown_ids_rejected(api):
    client, _ = api
    scenario = client.post('/api/demo-lab/scenarios', json={}).json()['data']
    assert client.patch(f"/api/demo-lab/scenarios/{scenario['id']}", json={'locator_revision': 2}).status_code == 422
    assert client.patch(f"/api/demo-lab/scenarios/{scenario['id']}", json={'unknown': True}).status_code == 422
    assert client.get('/api/demo-shop/missing').status_code == 404
    assert client.patch('/api/demo-lab/scenarios/missing', json={'visual_variant': True}).status_code == 404


def test_isolated_worker_can_reach_host_target_without_changing_saved_script(tmp_path):
    runner = PlaywrightRunner(str(tmp_path), container_image='runner:test')
    command = runner._worker_command('/tmp/test.py', str(tmp_path), {})
    assert '--add-host=host.docker.internal:host-gateway' in command
    # Exercise the injected helper without starting a browser or permitting host scripts.
    namespace = {}
    helper = runner._wrap_script('', '/work').split('# Capture final')[0]
    from playwright.sync_api import Page
    original = Page.goto
    try:
        exec(helper, namespace)
        assert namespace['_worker_target_url']('http://127.0.0.1:3000/api/demo-shop/abc') == 'http://host.docker.internal:3000/api/demo-shop/abc'
        assert namespace['_worker_target_url']('https://shop.example.test/a?x=1') == 'https://shop.example.test/a?x=1'
        assert namespace['_worker_target_url']('/relative') == '/relative'
    finally:
        Page.goto = original

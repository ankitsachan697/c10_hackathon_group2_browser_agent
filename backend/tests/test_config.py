import importlib

from backend.config import Settings
from n8n_workflows import deploy_workflows


def test_settings_do_not_supply_a_secret_token(monkeypatch):
    monkeypatch.delenv("N8N_BEARER_TOKEN", raising=False)

    assert Settings.from_env().n8n_bearer_token is None


def test_retry_limit_is_exactly_one(monkeypatch):
    monkeypatch.setenv("AUTO_REPAIR_RETRIES", "7")

    assert Settings.from_env().auto_repair_retries == 1


def test_server_can_start_without_a_product_name(monkeypatch):
    monkeypatch.delenv("PRODUCT_NAME", raising=False)

    server = importlib.import_module("backend.server")

    assert server.app.title == "API"


def test_workflow_deployment_requires_environment_configuration(monkeypatch):
    monkeypatch.setattr(deploy_workflows, "N8N_MCP_URL", None)
    monkeypatch.setattr(deploy_workflows, "N8N_BEARER_TOKEN", None)

    def unexpected_request(*args, **kwargs):
        raise AssertionError("A deployment request should require configuration")

    monkeypatch.setattr(deploy_workflows.requests, "post", unexpected_request)

    assert deploy_workflows.call_mcp_tool("search_workflows", {}) == {
        "error": "n8n MCP endpoint and bearer token are not configured"
    }

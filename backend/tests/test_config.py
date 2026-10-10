import importlib
import json

from backend.config import Settings, load_application_config
from n8n_workflows import deploy_workflows


def test_settings_do_not_supply_a_secret_token(monkeypatch):
    monkeypatch.delenv("N8N_BEARER_TOKEN", raising=False)

    assert Settings.from_env().n8n_bearer_token is None


def test_tracked_application_config_supplies_non_secret_defaults(tmp_path, monkeypatch):
    config_path = tmp_path / "application.json"
    config_path.write_text(json.dumps({
        "backend": {"internalUrl": "http://backend.internal:8000"},
        "runner": {"timeoutSeconds": 75},
        "n8n": {
            "mcpUrl": "https://n8n.example.test/mcp",
            "discoveryAgentId": "discovery-id",
            "repairAgentId": "repair-id",
            "visualAgentId": "visual-id",
            "generationEnabled": True,
            "repairEnabled": True,
            "localRepairEnabled": False,
        },
    }))
    for name in ("N8N_MCP_URL", "N8N_DISCOVERY_AGENT_ID", "RUNNER_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env(config_path)

    assert load_application_config(config_path)["backend"]["internalUrl"] == "http://backend.internal:8000"
    assert settings.backend_internal_url == "http://backend.internal:8000"
    assert settings.runner_timeout_seconds == 75
    assert settings.n8n_mcp_url == "https://n8n.example.test/mcp"
    assert settings.n8n_discovery_agent_id == "discovery-id"
    assert settings.n8n_repair_agent_id == "repair-id"
    assert settings.n8n_visual_agent_id == "visual-id"
    assert settings.enable_n8n_generation is True
    assert settings.enable_n8n_repair is True


def test_environment_overrides_tracked_application_config(tmp_path, monkeypatch):
    config_path = tmp_path / "application.json"
    config_path.write_text(json.dumps({
        "runner": {"timeoutSeconds": 60},
        "n8n": {"mcpUrl": "https://tracked.example.test/mcp", "generationEnabled": False},
    }))
    monkeypatch.setenv("RUNNER_TIMEOUT_SECONDS", "91")
    monkeypatch.setenv("N8N_MCP_URL", "https://override.example.test/mcp")
    monkeypatch.setenv("ENABLE_N8N_GENERATION", "true")

    settings = Settings.from_env(config_path)

    assert settings.runner_timeout_seconds == 91
    assert settings.n8n_mcp_url == "https://override.example.test/mcp"
    assert settings.enable_n8n_generation is True


def test_tracked_application_config_cannot_supply_secrets(tmp_path, monkeypatch):
    config_path = tmp_path / "application.json"
    config_path.write_text(json.dumps({
        "n8n": {"bearerToken": "tracked-token"},
        "security": {"credentialEncryptionKey": "tracked-key"},
    }))
    monkeypatch.delenv("N8N_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)

    settings = Settings.from_env(config_path)

    assert settings.n8n_bearer_token is None
    assert settings.credential_encryption_key is None


def test_retry_limit_is_exactly_one(monkeypatch):
    monkeypatch.setenv("AUTO_REPAIR_RETRIES", "7")

    assert Settings.from_env().auto_repair_retries == 1


def test_server_uses_tracked_product_name_without_an_environment_override(monkeypatch):
    monkeypatch.delenv("PRODUCT_NAME", raising=False)

    server = importlib.import_module("backend.server")

    assert server.app.title == "Outskill Browser Automation Studio"


def test_workflow_deployment_requires_environment_configuration(monkeypatch):
    monkeypatch.setattr(deploy_workflows, "N8N_MCP_URL", None)
    monkeypatch.setattr(deploy_workflows, "N8N_BEARER_TOKEN", None)

    def unexpected_request(*args, **kwargs):
        raise AssertionError("A deployment request should require configuration")

    monkeypatch.setattr(deploy_workflows.requests, "post", unexpected_request)

    assert deploy_workflows.call_mcp_tool("search_workflows", {}) == {
        "error": "n8n MCP endpoint, bearer token, and timeout are required"
    }


def test_workflow_deployment_requires_configured_timeout(monkeypatch):
    monkeypatch.setattr(deploy_workflows, "N8N_MCP_URL", "https://n8n.example.test/mcp")
    monkeypatch.setattr(deploy_workflows, "N8N_BEARER_TOKEN", "configured-token")
    monkeypatch.setattr(deploy_workflows, "N8N_TIMEOUT_SECONDS", None)

    assert deploy_workflows.call_mcp_tool("search_workflows", {}) == {
        "error": "n8n MCP endpoint, bearer token, and timeout are required"
    }

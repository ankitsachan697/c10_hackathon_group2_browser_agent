from dataclasses import replace
from types import SimpleNamespace

import pytest

from backend import server
from backend.config import Settings
from backend.n8n_client import N8nClient
import test_suite_manager


def test_operational_settings_use_tracked_non_secret_defaults(monkeypatch):
    for name in (
        "RUNNER_TIMEOUT_SECONDS",
        "PLAYWRIGHT_CDP_ENDPOINT",
        "PLAYWRIGHT_CDP_TIMEOUT_SECONDS",
        "VISUAL_DIFF_THRESHOLD",
        "VISUAL_TOLERANCE_PERCENT",
        "SCHEDULER_TIMEZONE",
        "N8N_MODEL",
        "N8N_MAX_TOKENS",
        "N8N_TEMPERATURE",
        "N8N_TIMEOUT_SECONDS",
        "N8N_DISCOVERY_AGENT_ID",
        "N8N_REPAIR_AGENT_ID",
        "N8N_VISUAL_AGENT_ID",
        "ENABLE_N8N_GENERATION",
        "ENABLE_N8N_REPAIR",
        "ENABLE_LOCAL_REPAIR",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.runner_timeout_seconds == 60
    assert settings.playwright_cdp_endpoint is None
    assert settings.playwright_cdp_timeout_seconds == 30
    assert settings.visual_diff_threshold == 0.1
    assert settings.visual_tolerance_percent == 0.5
    assert settings.scheduler_timezone == "Asia/Kolkata"
    assert settings.n8n_model is None
    assert settings.n8n_max_tokens == 2000
    assert settings.n8n_temperature == 0.1
    assert settings.n8n_timeout_seconds == 30
    assert settings.n8n_discovery_agent_id == "QEzE1lGs9WbTU82H"
    assert settings.n8n_repair_agent_id == "p3Sh9BmTzLMC0f8A"
    assert settings.enable_n8n_generation is True
    assert settings.enable_n8n_repair is True
    assert settings.enable_local_repair is False


def test_operational_settings_validate_invalid_values(monkeypatch):
    monkeypatch.setenv("RUNNER_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="RUNNER_TIMEOUT_SECONDS"):
        Settings.from_env()


def test_n8n_generation_uses_configured_agent_and_limits(monkeypatch):
    monkeypatch.setenv("N8N_MCP_URL", "https://n8n.example.test/mcp")
    monkeypatch.setenv("N8N_BEARER_TOKEN", "configured-token")
    monkeypatch.setenv("N8N_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("N8N_MODEL", "configured-model")
    monkeypatch.setenv("N8N_MAX_TOKENS", "321")
    monkeypatch.setenv("N8N_TEMPERATURE", "0.15")
    monkeypatch.setenv("N8N_DISCOVERY_AGENT_ID", "discovery-agent")
    monkeypatch.setenv("ENABLE_N8N_GENERATION", "true")
    client = N8nClient(Settings.from_env())
    captured = {}

    def call_mcp_tool(tool_name, arguments):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        return {"ok": True, "response": {"python_script": "print('generated')", "discovered_steps": []}}

    monkeypatch.setattr(client, "call_mcp_tool", call_mcp_tool)

    result = client.generate_flow_script("https://target.example.test", "check page")

    assert captured["tool_name"] == "call_agent"
    assert captured["arguments"]["agentId"] == "discovery-agent"
    assert captured["arguments"]["model"] == "configured-model"
    assert captured["arguments"]["maxTokens"] == 321
    assert captured["arguments"]["temperature"] == 0.15
    assert result["agent_id"] == "discovery-agent"


def test_n8n_repair_uses_its_configured_feature_and_agent(monkeypatch):
    monkeypatch.setenv("N8N_REPAIR_AGENT_ID", "repair-agent")
    monkeypatch.setenv("N8N_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("ENABLE_N8N_REPAIR", "true")
    client = N8nClient(Settings.from_env())
    calls = []

    def call_n8n_agent(agent_id, prompt):
        calls.append((agent_id, prompt))
        return {"ok": True, "response": {"repaired_script": "print('repaired')"}}

    monkeypatch.setattr(client, "call_n8n_agent", call_n8n_agent)

    result = client.diagnose_and_repair("print('run')", "locator timeout")

    assert calls[0][0] == "repair-agent"
    assert result["agent_id"] == "repair-agent"


def test_generated_login_script_does_not_supply_demo_credentials():
    script = N8nClient(Settings.from_env()).generate_flow_script(
        "https://target.example.test", "login to the application", offline=True
    )["python_script"]

    assert 'os.environ.get("AUTH_USERNAME")' in script
    assert 'os.environ.get("AUTH_PASSWORD")' in script
    assert "testuser@example.com" not in script
    assert "SecurePass123!" not in script


def test_generated_login_script_asserts_quoted_expected_text():
    script = N8nClient(Settings.from_env()).generate_flow_script(
        "https://target.example.test", 'login and validate "Logged In Successfully"', offline=True
    )["python_script"]

    assert 'expected_text = "Logged In Successfully"' in script


def test_generated_login_script_satisfies_execution_policy():
    from backend.runner import validate_browser_script
    script = N8nClient(Settings.from_env()).generate_flow_script(
        "https://target.example.test", 'login and validate "Logged In Successfully"', {"has_auth": True}, offline=True
    )["python_script"]
    validate_browser_script(script)
    assert "page.get_by_text(expected_text, exact=False).wait_for" in script


@pytest.mark.asyncio
async def test_saved_script_run_uses_configured_runner_and_visual_settings(monkeypatch):
    configured_settings = SimpleNamespace(
        auto_repair_retries=1,
        runner_timeout_seconds=47,
        visual_diff_threshold=0.23,
        visual_tolerance_percent=0.75,
    )
    runner_calls = []
    visual_calls = []

    async def execute_script(**kwargs):
        runner_calls.append(kwargs)
        return {
            "passed": True,
            "status": "PASSED",
            "screenshots": ["result.png"],
            "run_dir": "/tmp/run",
            "run_id": "run-id",
            "duration_seconds": 1.0,
            "video": None,
        }

    def handle_visual_baseline_lifecycle(**kwargs):
        visual_calls.append(kwargs)
        return {"status": "COMPLETED", "summary": "checked"}

    monkeypatch.setattr(server, "settings", configured_settings)
    monkeypatch.setattr(server, "runner", SimpleNamespace(execute_script=execute_script))
    monkeypatch.setattr(
        server,
        "suite_manager",
        SimpleNamespace(
            handle_visual_baseline_lifecycle=handle_visual_baseline_lifecycle,
            record_run=lambda record: None,
        ),
    )

    with pytest.raises(server.HTTPException) as error:
        await server.execute_direct_script(
            server.ExecuteScriptRequest(
                script="print('saved')", url="https://target.example.test", timeout_seconds=47, auto_heal=False
            )
        )

    assert error.value.status_code == 410
    assert runner_calls == []
    assert visual_calls == []


def test_suite_manager_uses_the_configured_artifact_root_and_starts_empty(tmp_path):
    manager = test_suite_manager.TestSuiteManager(
        suites_dir=tmp_path / "suites",
        artifacts_root=tmp_path / "artifacts",
    )

    assert manager.get_test_cases() == []
    assert manager.baselines_dir == tmp_path / "artifacts" / "baselines"

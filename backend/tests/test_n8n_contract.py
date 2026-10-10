import json

import pytest

from backend.config import Settings
from backend.n8n_client import N8nClient


def client(monkeypatch, *, token=None, generation=True, visual=True):
    monkeypatch.setenv("ENABLE_N8N_GENERATION", str(generation).lower())
    monkeypatch.setenv("ENABLE_N8N_VISUAL", str(visual).lower())
    if token:
        monkeypatch.setenv("N8N_BEARER_TOKEN", token)
    else:
        monkeypatch.delenv("N8N_BEARER_TOKEN", raising=False)
    return N8nClient(Settings.from_env())


def test_generation_without_runtime_token_fails_instead_of_synthesizing(monkeypatch):
    from backend.n8n_client import AgentError

    agent = client(monkeypatch)
    with pytest.raises(AgentError) as raised:
        agent.generate_flow_script("https://example.test", "log in")
    assert raised.value.code == "AGENT_NOT_CONFIGURED"


def test_disabled_generation_fails_even_with_token(monkeypatch):
    from backend.n8n_client import AgentError

    agent = client(monkeypatch, token="test-token", generation=False)
    with pytest.raises(AgentError) as raised:
        agent.generate_flow_script("https://example.test", "log in")
    assert raised.value.code == "AGENT_NOT_CONFIGURED"


def test_mcp_error_does_not_produce_local_script(monkeypatch):
    from backend.n8n_client import AgentError

    agent = client(monkeypatch, token="test-token")
    monkeypatch.setattr(agent, "call_mcp_tool", lambda *args: {"error": "upstream timeout"})
    with pytest.raises(AgentError) as raised:
        agent.generate_flow_script("https://example.test", "log in")
    assert raised.value.code == "AGENT_UNAVAILABLE"


def test_malformed_agent_output_fails_visibly(monkeypatch):
    from backend.n8n_client import AgentError

    agent = client(monkeypatch, token="test-token")
    monkeypatch.setattr(agent, "call_mcp_tool", lambda *args: {"content": [{"type": "text", "text": "not a script"}]})
    with pytest.raises(AgentError) as raised:
        agent.generate_flow_script("https://example.test", "log in")
    assert raised.value.code == "AGENT_RESPONSE_INVALID"


def test_standard_mcp_text_response_generates_script(monkeypatch):
    agent = client(monkeypatch, token="test-token")
    payload = {"python_script": "print('generated')", "discovered_steps": ["open page"]}
    monkeypatch.setattr(agent, "call_mcp_tool", lambda *args: {"content": [{"type": "text", "text": json.dumps(payload)}]})

    result = agent.generate_flow_script("https://example.test", "inspect page")

    assert result["python_script"] == "print('generated')"
    assert result["discovered_steps"] == ["open page"]
    assert result["agent_source"].startswith("n8n")


def test_discovery_accepts_json_code_fence_and_requests_structured_output(monkeypatch):
    agent = client(monkeypatch, token="test-token")
    prompts = []
    payload = {"python_script": "print('generated')", "discovered_steps": ["open page"]}
    monkeypatch.setattr(agent, "call_n8n_agent", lambda _agent_id, prompt: prompts.append(prompt) or {
        "response": "```json\n" + json.dumps(payload) + "\n```"
    })

    result = agent.generate_flow_script("https://example.test", "inspect page", {"has_auth": True})

    assert result["python_script"] == "print('generated')"
    assert result["discovered_steps"] == ["open page"]
    assert "discovered_steps" in prompts[0] and "python_script" in prompts[0]
    assert "JSON" in prompts[0]
    assert "get_by_label" in prompts[0]
    assert "get_by_role" in prompts[0]
    assert "label=" in prompts[0]
    assert "button[type='submit']" in prompts[0]


def test_explicit_offline_generation_is_labelled(monkeypatch):
    agent = client(monkeypatch)

    result = agent.generate_flow_script("https://example.test", "log in", offline=True)

    assert result["agent_source"] == "Local resilient synthesizer"
    assert "python_script" in result


def test_visual_agent_gets_only_bounded_safe_metrics(monkeypatch):
    agent = client(monkeypatch, token="test-token")
    captured = []
    monkeypatch.setattr(agent, "call_n8n_agent", lambda agent_id, prompt: captured.append((agent_id, prompt)) or {"response": {"summary": "Layout matches"}})

    result = agent.review_visual({"status": "MATCH", "mismatch_percentage": 0.1, "password": "private-value", "dom": "x" * 9000})

    assert result["summary"] == "Layout matches"
    assert captured[0][0] == agent.settings.n8n_visual_agent_id
    assert "private-value" not in captured[0][1]
    assert len(captured[0][1]) < 1000


def test_repair_mcp_failure_is_not_silently_replaced(monkeypatch):
    from backend.n8n_client import AgentError
    agent = client(monkeypatch, token="test-token")
    monkeypatch.setenv("ENABLE_N8N_REPAIR", "true")
    agent.settings = Settings.from_env()
    monkeypatch.setattr(agent, "call_n8n_agent", lambda *args: (_ for _ in ()).throw(AgentError("AGENT_UNAVAILABLE", "unreachable")))
    with pytest.raises(AgentError) as raised:
        agent.diagnose_and_repair("print('run')", "locator timeout")
    assert raised.value.code == "AGENT_UNAVAILABLE"

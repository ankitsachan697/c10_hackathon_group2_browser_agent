import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "n8n_workflows"


def load(name: str):
    return json.loads((WORKFLOWS / name).read_text())


def model_node(workflow):
    return next(node for node in workflow["nodes"] if node["type"].endswith("lmChatOpenAi"))


def test_generation_and_repair_workflows_are_configurable_and_secret_free():
    for filename in ("flow_discovery_and_generator.json", "error_diagnosis_and_repair.json"):
        workflow = load(filename)
        encoded = json.dumps(workflow)
        model = model_node(workflow)["parameters"]
        assert "$env.N8N_MODEL" in model["model"]["value"]
        assert "$env.N8N_MAX_TOKENS" in str(model["options"]["maxTokens"])
        assert "$env.N8N_TEMPERATURE" in str(model["options"]["temperature"])
        assert "credentials" not in model_node(workflow)
        assert "p3HjGydOnUih77wo" not in encoded
        assert "valid JSON object only" in encoded


def test_repair_contract_uses_only_bounded_failure_packet_fields():
    workflow = load("error_diagnosis_and_repair.json")
    prompt = next(node for node in workflow["nodes"] if node["id"] == "ai-agent-repair")["parameters"]["text"]
    for field in ("failure_category", "error_excerpt", "dom_excerpt", "script_excerpt", "selectors"):
        assert field in prompt
    assert "errorTrace" not in prompt
    assert "$json.body.script +" not in prompt


def test_visual_workflow_is_reference_only_and_not_runtime_active():
    workflow = load("visual_regression_monitor.json")
    assert workflow["active"] is False
    assert workflow["settings"]["runtimePath"] is False

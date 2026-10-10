# n8n agent contracts

n8n is optional and has two runtime responsibilities: explicit journey generation and one diagnosis/repair attempt after an eligible saved-script failure. Configure host, token, published agent IDs, model, token limit, temperature, and timeout at deployment.

## Generation

Input is `{ "target_url": "...", "objective": "...", "credentials_meta": {} }`. Output must be a JSON object containing `discovered_steps` (string array), `selectors` (object), and `python_script` (string). Generation runs only after the user confirms the create-journey review step. Generated scripts read credentials from environment variables.

## Repair

Input is a length-bounded, redacted object containing `failure_category`, `error_excerpt`, `dom_excerpt`, `script_excerpt`, and `selectors`. Output must contain `root_cause`, `failure_category`, `recommended_fix`, `diff_summary`, and `repaired_script`.

The backend determines eligibility, validates the response, and executes the repaired script once. Missing, malformed, timed-out, or unsuccessful repairs become `NEEDS_ATTENTION`.

## Visual comparison

Visual comparison is local and deterministic. `visual_regression_monitor.json` is inactive reference material and is not part of the runtime request path.

## Validate and deploy

```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_n8n_workflows.py -q
python n8n_workflows/deploy_workflows.py --validate
```

After import, bind an OpenAI credential in n8n and set `N8N_MODEL`, `N8N_MAX_TOKENS`, and `N8N_TEMPERATURE` in its deployment environment. Store published IDs in the application environment as `N8N_DISCOVERY_AGENT_ID` and `N8N_REPAIR_AGENT_ID`.

# n8n agent contracts

n8n has three configured runtime responsibilities: discovery/script generation for a newly created journey, one diagnosis/repair attempt after an eligible failure, and optional bounded visual review after screenshot comparison. Configure the backend runtime token, published agent IDs, model, token limit, temperature, and timeout at deployment. Without a token, normal generation fails visibly; local generation requires an explicit offline selection.

## Generation

Input includes target URL, objective, and `has_auth` metadata only. Output must include `discovered_steps` (string array) and `python_script` (string). Generation runs once when the user submits the one-page form, followed by an automatic first run of the saved script. Generated scripts read credentials from environment variables.

## Repair

Input is a length-bounded, redacted object containing `failure_category`, `error_excerpt`, `dom_excerpt`, `script_excerpt`, and `selectors`. Output must contain `root_cause`, `failure_category`, `recommended_fix`, `diff_summary`, and `repaired_script`.

The backend determines eligibility, validates the response, and executes the repaired script once. Missing, malformed, timed-out, or unsuccessful repairs become `NEEDS_ATTENTION`.

## Visual comparison

Visual comparison is local and deterministic. When enabled and authenticated, the published visual agent receives only bounded status, mismatch metrics, threshold, and a baseline key; it never receives the full screenshot, DOM, or credentials. A visual-agent failure is recorded separately from the functional run status. `visual_regression_monitor.json` is inactive reference material, not the runtime invocation path.

## Validate and deploy

```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_n8n_workflows.py -q
python n8n_workflows/deploy_workflows.py --validate
```

After import, bind the model credential in n8n and set model, token, and temperature limits in its deployment environment. The application reads published agent IDs and safe flags from `config/application.json`; only `N8N_BEARER_TOKEN` must be injected as a backend runtime secret. The private live agent definitions were not inspectable in this workspace, so validate their published MCP response contracts in an authenticated environment before a demo.

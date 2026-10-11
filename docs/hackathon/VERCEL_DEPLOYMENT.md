# Group2 free Vercel deployment

The initial cloud release serves the Next.js Studio and a persistent Python API on the approved `testing-group1` Hobby account. The backend runs in a named Vercel Sandbox, not in a short-lived Python Function. Its SQLite database, credential key and private artifacts survive Sandbox stop/resume. Production and preview use separate named controllers.

## Deploy

1. Add repository secrets `VERCEL_TOKEN` and `N8N_BEARER_TOKEN` in GitHub Settings → Secrets and variables → Actions. The Vercel token needs access to the approved account/project.
2. Open Actions → **Deploy Studio to Vercel** → Run workflow on `demo_master`.
3. Read the deployment URL in the workflow summary. Open it while signed into the owning Vercel account. Vercel Authentication protects the Studio, including its API gateway; raw Sandbox API endpoints independently require server-side authorization.

The workflow verifies the account is still Hobby, preserves existing controller keys, maps n8n authentication privately into Vercel server environment variables, and deploys only allowlisted frontend/source/configuration files. It never puts the Vercel deployment token in the application, and does not upload local `.env` files, databases, captured credentials or local run history.

## Current release boundaries

- Projects, history APIs, configuration and dashboard data are served by the real Python backend. New cloud state starts empty.
- Remote headless execution uses isolated ephemeral Playwright workers with session admission. The controller never executes generated code. A first journey invokes n8n discovery; saved replays use the saved script and may invoke repair once for eligible failures. Local browser execution remains unchanged.
- Cloud scheduled regression and remote headed pairing execution are not enabled in this initial release.
- A cold controller startup installs its pinned Python dependencies; the first API request may take longer. Subsequent source-only updates reuse its virtual environment.
- Sandbox sessions stop after 40 minutes; the next authenticated API request resumes the controller from its filesystem snapshot. Free usage quotas can pause service; no paid upgrade, Pro trial or billing changes are requested. Hobby is for personal/non-commercial use.
- n8n and OpenRouter model usage are separate from Vercel's free quotas. A configured token is not proof an agent has executed; inspect actual activity records and run evidence. The published agents now use the existing OpenRouter connection because MCP execution with the managed Gateway returned `Unauthorized`. Publishing an agent setting/instruction change does not require redeploying Vercel. See [published agent versions](agent-versions.json).

Do not attach a custom domain while using `all_except_custom_domains` protection without first protecting that domain independently. Never disable deployment protection while this shared Studio can trigger backend mutations.

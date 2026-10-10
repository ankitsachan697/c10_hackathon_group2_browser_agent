# API reference

The API uses `{ "data": ..., "error": null, "meta": {} }`. Failures use the same envelope with `data: null` and a structured error.

## Projects and environments

- `GET|POST /api/projects` — list/search or create projects.
- `GET /api/projects/{id}` — retrieve a project.
- `POST /api/projects/{id}/run` — run all saved project journeys.
- `GET /api/projects/{id}/deletion-impact` — preview cascade counts.
- `DELETE /api/projects/{id}` — cascade resources and move evidence to trash.
- `GET|POST /api/environments` — list or create target environments.

## Journeys

- `GET|POST /api/journeys` — list or create saved journeys.
- `POST /api/journeys/generate` — explicitly generate and save a journey.
- `GET|DELETE /api/journeys/{id}` — inspect or delete.
- `PUT /api/journeys/{id}/credentials` — replace the encrypted username/password pair without returning it.
- `POST /api/journeys/{id}/run` — execute the saved script directly.

Journey create and generate requests optionally accept `username` and `password`. They must be supplied together. Responses never return either value or the stored ciphertext; `has_credentials` indicates whether an encrypted credential pair exists. The backend creates a persistent private encryption key beside SQLite automatically. If that key is missing for existing credentials, the API returns `CREDENTIAL_VAULT_UNAVAILABLE` without persisting plaintext.

## Runs and evidence

- `GET /api/runs` — list history.
- `GET /api/runs/{id}` — retrieve a run with attempts and artifacts.
- `POST /api/runs/{id}/rerun` with mode `current` or `snapshot`.
- `DELETE /api/runs/{id}` — delete and move evidence to trash.
- `GET /api/artifacts/{artifact_id}` — download evidence by stable ID.

Operational endpoints never generate scripts. `/api/autonomous-run` is a `410 Gone` migration response.

## Schedules and system

- `GET|POST /api/schedules`; `PATCH|DELETE /api/schedules/{id}`.
- `POST /api/schedules/{id}/run` — run immediately.
- `GET /api/health`, `GET /api/config/public`, and `GET /api/docs`.

The web application uses same-origin `/api/*`; Next.js proxies to `backend.internalUrl` from `config/application.json` or the `BACKEND_INTERNAL_URL` deployment override.

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
- `GET|PATCH|DELETE /api/journeys/{id}` — inspect, update, or delete.
- `POST /api/journeys/{id}/run` — execute the saved script directly.

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

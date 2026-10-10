"""Idempotent import for the prototype JSON registry."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .database import Database
    from .repositories import JourneyRepository, ProjectRepository, RunRepository
except ImportError:
    from database import Database
    from repositories import JourneyRepository, ProjectRepository, RunRepository


@dataclass
class ImportSummary:
    projects: int = 0
    journeys: int = 0
    runs: int = 0
    warnings: list[str] = field(default_factory=list)


def _read(path: str | Path, summary: ImportSummary):
    source = Path(path)
    if not source.exists():
        return []
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError) as error:
        summary.warnings.append(f"{source.name}: {error}")
        return []


def _marked(database: Database, source: str, legacy_id: str) -> bool:
    with database.connect() as connection:
        return connection.execute("SELECT 1 FROM import_markers WHERE source_key=? AND legacy_id=?", (source, legacy_id)).fetchone() is not None


def _mark(database: Database, source: str, legacy_id: str, imported_id: str) -> None:
    with database.transaction() as connection:
        connection.execute("INSERT OR IGNORE INTO import_markers(source_key,legacy_id,imported_id) VALUES (?,?,?)", (source, legacy_id, imported_id))


def import_legacy_json(database: Database, cases_path: str | Path, runs_path: str | Path) -> ImportSummary:
    database.initialize()
    summary = ImportSummary()
    projects, journeys, runs_repo = ProjectRepository(database), JourneyRepository(database), RunRepository(database)

    for index, case in enumerate(_read(cases_path, summary)):
        legacy_id = str(case.get("id") or f"case-{index}")
        if _marked(database, "case", legacy_id):
            continue
        project_name = str(case.get("project") or "General")
        project = projects.find_by_name(project_name)
        if not project:
            project = projects.create({"name": project_name})
            summary.projects += 1
        journey = journeys.create({
            "project_id": project["id"], "name": case.get("name") or legacy_id,
            "objective": case.get("objective", ""), "target_url": case.get("target_url") or case.get("url") or "",
            "script": case.get("script", ""),
        })
        _mark(database, "case", legacy_id, journey["id"])
        summary.journeys += 1

    known_journeys = journeys.list()
    for index, item in enumerate(_read(runs_path, summary)):
        legacy_id = str(item.get("run_id") or item.get("id") or f"run-{index}")
        if _marked(database, "run", legacy_id):
            continue
        journey = next((candidate for candidate in known_journeys if candidate["name"] == item.get("name") or candidate["target_url"] == item.get("url")), None)
        run = runs_repo.create({
            "journey_id": journey["id"] if journey else None, "status": item.get("status", "FAILED"),
            "trigger_source": item.get("trigger_source", "ON_DEMAND"),
            "script_snapshot": journey["script"] if journey else item.get("script", ""),
            "script_version": journey["script_version"] if journey else 1,
            "attempt_count": item.get("attempts", 0),
        })
        _mark(database, "run", legacy_id, run["id"])
        summary.runs += 1
    return summary

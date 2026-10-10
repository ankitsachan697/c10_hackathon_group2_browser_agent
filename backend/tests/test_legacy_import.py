import json
from pathlib import Path

from backend.database import Database
from backend.legacy_import import import_legacy_json
from backend.repositories import JourneyRepository, ProjectRepository, RunRepository


def test_missing_and_corrupt_legacy_files_are_non_fatal(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    corrupt = tmp_path / "runs.json"
    corrupt.write_text("not-json", encoding="utf-8")

    summary = import_legacy_json(database, tmp_path / "missing.json", corrupt)

    assert summary.projects == 0
    assert summary.journeys == 0
    assert summary.runs == 0
    assert len(summary.warnings) == 1


def test_legacy_import_is_idempotent(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    cases = tmp_path / "cases.json"
    runs = tmp_path / "runs.json"
    cases.write_text(json.dumps([{
        "id": "legacy-case", "project": "Payments", "name": "Pay", "target_url": "https://pay.invalid",
        "objective": "Pay invoice", "script": "print('pay')"
    }]), encoding="utf-8")
    runs.write_text(json.dumps([{
        "run_id": "legacy-run", "name": "Pay", "url": "https://pay.invalid", "status": "PASSED",
        "timestamp": "2026-01-01 01:02:03", "attempts": 1
    }]), encoding="utf-8")

    first = import_legacy_json(database, cases, runs)
    second = import_legacy_json(database, cases, runs)

    assert (first.projects, first.journeys, first.runs) == (1, 1, 1)
    assert (second.projects, second.journeys, second.runs) == (0, 0, 0)
    assert len(ProjectRepository(database).list()) == 1
    assert len(JourneyRepository(database).list()) == 1
    assert len(RunRepository(database).list()) == 1

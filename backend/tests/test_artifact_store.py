from pathlib import Path

import pytest

from backend.artifact_store import ArtifactStore
from backend.database import Database
from backend.repositories import ArtifactRepository, RunRepository


def _store(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    run = RunRepository(database).create({"status": "FAILED", "script_snapshot": "pass", "script_version": 1})
    return database, run, ArtifactStore(tmp_path / "artifacts", tmp_path / "trash", ArtifactRepository(database))


def test_resolve_rejects_path_traversal(tmp_path):
    database, run, store = _store(tmp_path)
    artifact = ArtifactRepository(database).create({"run_id": run["id"], "kind": "log", "storage_path": "../secret.txt"})

    with pytest.raises(ValueError, match="artifact root"):
        store.resolve(artifact["id"])


def test_trash_run_moves_files_and_preserves_metadata(tmp_path):
    database, run, store = _store(tmp_path)
    source = tmp_path / "artifacts" / run["id"] / "shot.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"png")
    artifact = ArtifactRepository(database).create({
        "run_id": run["id"], "kind": "screenshot", "storage_path": f"{run['id']}/shot.png"
    })

    moved = store.trash_run(run["id"])

    assert moved == 1
    assert not source.exists()
    assert (tmp_path / "trash" / run["id"] / "shot.png").exists()
    updated = ArtifactRepository(database).get(artifact["id"])
    assert updated["deleted_at"] is not None
    assert updated["storage_path"] == f"{run['id']}/shot.png"


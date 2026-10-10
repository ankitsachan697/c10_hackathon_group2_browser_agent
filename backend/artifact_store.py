"""Root-safe filesystem operations for run evidence."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from .repositories import ArtifactRepository
except ImportError:
    from repositories import ArtifactRepository


class ArtifactStore:
    def __init__(self, root: str | Path, trash_root: str | Path, repository: ArtifactRepository):
        self.root = Path(root).resolve()
        self.trash_root = Path(trash_root).resolve()
        self.repository = repository
        self.root.mkdir(parents=True, exist_ok=True)
        self.trash_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(root: Path, relative: str) -> Path:
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Artifact path escapes configured artifact root")
        return candidate

    def resolve(self, artifact_id: str) -> Path:
        artifact = self.repository.get(artifact_id)
        if not artifact:
            raise FileNotFoundError(artifact_id)
        return self._safe(self.root, artifact["storage_path"])

    def trash_run(self, run_id: str) -> int:
        moved = 0
        deleted_at = datetime.now(timezone.utc).isoformat()
        for artifact in self.repository.list_for_run(run_id):
            source = self._safe(self.root, artifact["storage_path"])
            destination = self._safe(self.trash_root, artifact["storage_path"])
            if source.exists() and source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                moved += 1
            self.repository.mark_deleted(artifact["id"], deleted_at)
        run_dir = self._safe(self.root, run_id)
        if run_dir.exists() and not any(run_dir.iterdir()):
            run_dir.rmdir()
        return moved

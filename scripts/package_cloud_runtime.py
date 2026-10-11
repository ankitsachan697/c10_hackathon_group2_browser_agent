"""Build an allowlisted, deterministic runtime archive without local state."""
import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path


BACKEND_MODULES = (
    "server", "config", "database", "models", "repositories", "runner",
    "action_events", "artifact_store", "credential_vault", "n8n_client",
    "scheduler", "test_suite_manager", "legacy_import", "generation", "orchestrator",
    "page_controls", "failure_context", "event_store", "redaction", "visual_diff",
    "visual_review", "companion_registry", "cdp_relay",
    "cloud_policy", "cloud_auth", "cloud_lifecycle", "sandbox_transport", "sandbox_runner", "cloud_jobs", "cloud_media",
)
API_MODULES = (
    "__init__", "context", "system", "projects", "journeys", "runs", "schedules",
    "environments", "operations", "companions", "demo_lab", "media",
)
RUNTIME_FILES = (
    *(f"backend/{name}.py" for name in BACKEND_MODULES),
    *(f"backend/api/{name}.py" for name in API_MODULES),
    "backend/requirements.txt", "config/application.json",
    "backend/demo_shop/index.html", "backend/demo_shop/shop.css", "backend/demo_shop/shop.js",
)


def package_runtime(repository_root: Path, output_dir: Path) -> dict:
    root = repository_root.resolve(strict=True)
    files = sorted(RUNTIME_FILES)
    # Validate the entire allowlist before opening output. Never follow symlinks.
    for name in files:
        candidate = root / name
        if any(parent.is_symlink() for parent in (candidate, *candidate.parents)
               if parent != root and root in parent.parents):
            raise ValueError(f"Runtime symlink is not allowed: {name}")
    for name in files:
        candidate = root / name
        if not candidate.is_file():
            raise ValueError(f"Missing required runtime file: {name}")
        if not candidate.resolve(strict=True).is_relative_to(root):
            raise ValueError(f"Runtime path escapes repository: {name}")
    output = output_dir.resolve()
    if output == root or output in root.parents:
        raise ValueError("Choose a dedicated runtime output directory")
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / "group2-runtime.tar.gz"
    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for name in files:
                    candidate = root / name
                    info = tarfile.TarInfo(name)
                    info.size = candidate.stat().st_size
                    info.mode = 0o644
                    with candidate.open("rb") as source:
                        archive.addfile(info, source)
    return {"archive_path": str(archive_path),
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "files": files}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package_runtime(args.repository_root, args.output_dir), indent=2))

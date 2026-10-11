import hashlib
import importlib
import tarfile
from pathlib import Path

import pytest


def package_runtime(*args):
    module = importlib.import_module("scripts.package_cloud_runtime")
    return module.package_runtime(*args)


def test_bundle_contains_required_backend_and_config_but_no_private_history(tmp_path):
    root = Path(__file__).resolve().parents[2]
    bundle = package_runtime(root, tmp_path)
    with tarfile.open(bundle["archive_path"]) as archive:
        names = archive.getnames()
    assert {"backend/server.py", "backend/runner.py", "backend/requirements.txt",
            "config/application.json", "backend/demo_shop/index.html",
            "backend/demo_shop/shop.js", "backend/demo_shop/shop.css"} <= set(names)
    assert names == bundle["files"]
    assert not any(part in {".env", ".venv", "tests", "docs", "artifacts", "test_suites"}
                   for name in names for part in Path(name).parts)
    assert not any(Path(name).suffix in {".db", ".sqlite", ".sqlite3", ".key"} for name in names)
    assert not any(".env" in name for name in names)
    assert bundle["sha256"] == hashlib.sha256(Path(bundle["archive_path"]).read_bytes()).hexdigest()


def test_bundle_rejects_symlinks_outside_repository(tmp_path):
    root = tmp_path / "repo"
    (root / "backend").mkdir(parents=True)
    external = tmp_path / "private.py"
    external.write_text("password = 'must-not-ship'", encoding="utf-8")
    (root / "backend/server.py").symlink_to(external)
    with pytest.raises(ValueError, match="symlink"):
        package_runtime(root, tmp_path / "bundle")


def test_identical_runtime_produces_identical_archive(tmp_path):
    root = Path(__file__).resolve().parents[2]
    first = package_runtime(root, tmp_path / "one")
    second = package_runtime(root, tmp_path / "two")
    assert first["sha256"] == second["sha256"]


def test_missing_runtime_file_prevents_partial_bundle(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValueError, match="required"):
        package_runtime(root, tmp_path / "bundle")

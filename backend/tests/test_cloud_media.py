from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.cloud_media import issue_artifact_capability, verify_artifact_capability, media_path
from backend.api.media import router


def test_signed_url_is_artifact_scoped_and_expires():
    token = issue_artifact_capability("art_one", "synthetic-key", now=100)
    assert verify_artifact_capability("art_one", "synthetic-key", token, now=200)
    assert not verify_artifact_capability("art_two", "synthetic-key", token, now=200)
    assert not verify_artifact_capability("art_one", "synthetic-key", token, now=221)
    assert not verify_artifact_capability("art_one", "wrong", token, now=200)


def test_media_denies_deleted_files_traversal_and_symlinks(tmp_path):
    (tmp_path / "valid.png").write_bytes(b"synthetic")
    assert media_path(tmp_path, {"storage_path": "valid.png"}) == tmp_path / "valid.png"
    for artifact in ({"storage_path": "../outside.png"}, {"storage_path": "valid.png", "deleted_at": "now"}):
        with pytest.raises(FileNotFoundError): media_path(tmp_path, artifact)
    (tmp_path / "linked.png").symlink_to(tmp_path / "valid.png")
    with pytest.raises(FileNotFoundError): media_path(tmp_path, {"storage_path": "linked.png"})


def test_large_video_range_response(tmp_path):
    video = tmp_path / "session_video.webm"
    video.write_bytes(b"x" * (5 * 1024 * 1024))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.cloud_policy = SimpleNamespace(media_secret="synthetic-key")
    repo = SimpleNamespace(get=lambda identifier: {"storage_path": video.name, "media_type": "video/webm"} if identifier == "art_video" else None)
    app.state.services = SimpleNamespace(artifacts=SimpleNamespace(root=tmp_path, repository=repo))
    token = issue_artifact_capability("art_video", "synthetic-key")
    with TestClient(app) as client:
        assert client.get("/api/media/art_video?token=wrong").status_code == 403
        response = client.get(f"/api/media/art_video?token={token}", headers={"Range": "bytes=1024-2047"})
        assert response.status_code == 206 and len(response.content) == 1024
        assert response.headers["content-range"] == f"bytes 1024-2047/{video.stat().st_size}"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "no-store" in response.headers["cache-control"]

"""Short-lived, single-artifact read capabilities; never general API authority."""
import hashlib
import hmac
import re
import time
from pathlib import Path


def issue_artifact_capability(artifact_id: str, key: str, now=None) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", artifact_id):
        raise ValueError("Invalid artifact ID")
    expiry = int(time.time() if now is None else now) + 120
    signature = hmac.new(key.encode(), f"artifact-read:{artifact_id}:{expiry}".encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{signature}"


def verify_artifact_capability(artifact_id: str, key: str, token: str, now=None) -> bool:
    try:
        expiry, signature = token.split(".")
        expiry = int(expiry)
        current = int(time.time() if now is None else now)
        if not current <= expiry <= current + 120:
            return False
        expected = hmac.new(key.encode(), f"artifact-read:{artifact_id}:{expiry}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except (ValueError, TypeError, AttributeError):
        return False


def media_path(root: Path, artifact: dict | None) -> Path:
    if not artifact or artifact.get("deleted_at"):
        raise FileNotFoundError("Artifact is unavailable")
    root = root.resolve()
    candidate = root / artifact["storage_path"]
    if any(path.is_symlink() for path in (candidate, *candidate.parents) if path != root and root in path.parents):
        raise FileNotFoundError("Artifact is unavailable")
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise FileNotFoundError("Artifact is unavailable")
    return candidate

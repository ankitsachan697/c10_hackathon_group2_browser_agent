"""Fail-closed server-only policy for a trusted persistent controller."""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CloudPolicy:
    enabled: bool
    state_root: Path
    team_id: str
    project_id: str
    control_secret: str = field(repr=False)
    media_secret: str = field(repr=False)
    source_revision: str = ""
    origin: str = ""

    @classmethod
    def from_env(cls) -> "CloudPolicy":
        enabled = os.getenv("CLOUD_MODE", "false").lower() == "true"
        team = os.getenv("VERCEL_TEAM_ID", "")
        project = os.getenv("VERCEL_PROJECT_ID", "")
        control = os.getenv("CLOUD_CONTROL_SECRET", "")
        media = os.getenv("CLOUD_MEDIA_SECRET", "")
        if enabled:
            if team != "team_vX4hl0qHhzt1aKFxd5wVJ7bU" or not project.startswith("prj_"):
                raise ValueError("Cloud account/project scope is not configured")
            for name, value in (("CLOUD_CONTROL_SECRET", control), ("CLOUD_MEDIA_SECRET", media)):
                if len(value) < 32:
                    raise ValueError(f"{name} must be a server-only secret of at least 32 characters")
            if not os.getenv("CLOUD_STATE_ROOT"):
                raise ValueError("CLOUD_STATE_ROOT is required")
        return cls(enabled, Path(os.getenv("CLOUD_STATE_ROOT", "/vercel/sandbox/state")).resolve(),
                   team, project, control, media, os.getenv("CLOUD_SOURCE_REVISION", ""),
                   os.getenv("CLOUD_CONTROLLER_ORIGIN", ""))

    def sdk_credentials(self, minimum_lifetime: int = 0) -> dict:
        """Read privately refreshed SDK credentials; never expose them to a worker."""
        try:
            path = self.state_root / "sdk-credentials.json"
            if path.is_symlink():
                raise ValueError("Invalid SDK credentials path")
            value = json.loads(path.read_text(encoding="utf-8"))
            token = value["token"]
            payload = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if claims["owner_id"] != self.team_id or claims["project_id"] != self.project_id:
                raise ValueError("SDK credentials do not match the controller account/project")
            if claims["exp"] <= time.time() + minimum_lifetime:
                raise ValueError("SDK credentials expired or lack the required job budget; refresh the Studio session")
            return {"token": token, "team_id": self.team_id, "project_id": self.project_id}
        except ValueError:
            raise
        except (OSError, KeyError, TypeError, IndexError) as failure:
            raise ValueError("Scoped SDK credentials are unavailable; refresh the Studio session") from failure

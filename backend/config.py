"""Environment-backed runtime settings for Browser Automation Studio."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() or None if value else None


def _path_from_env(name: str, default: Path) -> Path:
    value = _optional_env(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def _int_from_env(name: str, default: int) -> int:
    value = _optional_env(name)
    return int(value) if value else default


def _float_from_env(name: str, default: float) -> float:
    value = _optional_env(name)
    return float(value) if value else default


def _bool_from_env(name: str, default: bool) -> bool:
    value = _optional_env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    artifacts_root: Path
    artifact_trash_root: Path
    product_name: str | None
    cors_origins: tuple[str, ...]
    runner_timeout_seconds: int
    visual_diff_threshold: float
    scheduler_timezone: str
    n8n_mcp_url: str | None
    n8n_bearer_token: str | None
    n8n_model: str | None
    n8n_max_tokens: int
    n8n_timeout_seconds: int
    auto_repair_retries: int
    enable_n8n_generation: bool
    enable_n8n_repair: bool

    @classmethod
    def from_env(cls) -> "Settings":
        artifacts_root = _path_from_env("ARTIFACTS_ROOT", PROJECT_ROOT / "artifacts")
        cors_origins = tuple(
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
        return cls(
            database_path=_path_from_env("DATABASE_PATH", PROJECT_ROOT / "data" / "browser_automation.db"),
            artifacts_root=artifacts_root,
            artifact_trash_root=_path_from_env("ARTIFACT_TRASH_ROOT", artifacts_root / ".trash"),
            product_name=_optional_env("PRODUCT_NAME"),
            cors_origins=cors_origins,
            runner_timeout_seconds=_int_from_env("RUNNER_TIMEOUT_SECONDS", 60),
            visual_diff_threshold=_float_from_env("VISUAL_DIFF_THRESHOLD", 0.1),
            scheduler_timezone=_optional_env("SCHEDULER_TIMEZONE") or "UTC",
            n8n_mcp_url=_optional_env("N8N_MCP_URL"),
            n8n_bearer_token=_optional_env("N8N_BEARER_TOKEN"),
            n8n_model=_optional_env("N8N_MODEL"),
            n8n_max_tokens=_int_from_env("N8N_MAX_TOKENS", 1000),
            n8n_timeout_seconds=_int_from_env("N8N_TIMEOUT_SECONDS", 30),
            auto_repair_retries=1,
            enable_n8n_generation=_bool_from_env("ENABLE_N8N_GENERATION", True),
            enable_n8n_repair=_bool_from_env("ENABLE_N8N_REPAIR", True),
        )

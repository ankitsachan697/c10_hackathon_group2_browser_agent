"""Environment-backed runtime settings for Browser Automation Studio."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() or None if value else None


def _path_from_env(name: str, default: Path) -> Path:
    value = _optional_env(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def _positive_int_from_env(name: str) -> int | None:
    value = _optional_env(name)
    if value is None:
        return None
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if number <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return number


def _fraction_from_env(name: str) -> float | None:
    value = _optional_env(name)
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be between 0 and 1") from error
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _bool_from_env(name: str) -> bool:
    value = _optional_env(name)
    if value is None:
        return False
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _timezone_from_env() -> str | None:
    timezone = _optional_env("SCHEDULER_TIMEZONE")
    if timezone is None:
        return None
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError("SCHEDULER_TIMEZONE must be a valid IANA timezone") from error
    return timezone


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    artifacts_root: Path
    artifact_trash_root: Path
    product_name: str | None
    cors_origins: tuple[str, ...]
    runner_timeout_seconds: int | None
    visual_diff_threshold: float | None
    visual_tolerance_percent: float | None
    scheduler_timezone: str | None
    n8n_mcp_url: str | None
    n8n_bearer_token: str | None
    n8n_model: str | None
    n8n_max_tokens: int | None
    n8n_timeout_seconds: int | None
    n8n_discovery_agent_id: str | None
    n8n_repair_agent_id: str | None
    n8n_visual_agent_id: str | None
    auto_repair_retries: int
    enable_n8n_generation: bool
    enable_n8n_repair: bool
    enable_local_repair: bool

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
            runner_timeout_seconds=_positive_int_from_env("RUNNER_TIMEOUT_SECONDS"),
            visual_diff_threshold=_fraction_from_env("VISUAL_DIFF_THRESHOLD"),
            visual_tolerance_percent=_fraction_from_env("VISUAL_TOLERANCE_PERCENT"),
            scheduler_timezone=_timezone_from_env(),
            n8n_mcp_url=_optional_env("N8N_MCP_URL"),
            n8n_bearer_token=_optional_env("N8N_BEARER_TOKEN"),
            n8n_model=_optional_env("N8N_MODEL"),
            n8n_max_tokens=_positive_int_from_env("N8N_MAX_TOKENS"),
            n8n_timeout_seconds=_positive_int_from_env("N8N_TIMEOUT_SECONDS"),
            n8n_discovery_agent_id=_optional_env("N8N_DISCOVERY_AGENT_ID"),
            n8n_repair_agent_id=_optional_env("N8N_REPAIR_AGENT_ID"),
            n8n_visual_agent_id=_optional_env("N8N_VISUAL_AGENT_ID"),
            auto_repair_retries=1,
            enable_n8n_generation=_bool_from_env("ENABLE_N8N_GENERATION"),
            enable_n8n_repair=_bool_from_env("ENABLE_N8N_REPAIR"),
            enable_local_repair=_bool_from_env("ENABLE_LOCAL_REPAIR"),
        )

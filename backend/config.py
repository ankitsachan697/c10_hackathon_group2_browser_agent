"""Tracked non-secret defaults with environment-backed runtime secrets."""

from __future__ import annotations

import json
import os
from typing import Any
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "application.json"


def load_application_config(path: Path | None = None) -> dict[str, Any]:
    """Load tracked non-secret configuration; secrets are intentionally ignored later."""
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        return {}
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid application configuration: {target}") from error
    if not isinstance(value, dict):
        raise ValueError("Application configuration root must be an object")
    return value


def _configured(config: dict[str, Any], *path: str, default: Any = None) -> Any:
    value: Any = config
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def _env_or_config(name: str, config: dict[str, Any], *path: str, default: Any = None) -> Any:
    value = _optional_env(name)
    return value if value is not None else _configured(config, *path, default=default)


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() or None if value else None


def _path_from_env(name: str, default: Path) -> Path:
    value = _optional_env(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def _positive_int(name: str, value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if number <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return number


def _fraction(name: str, value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be between 0 and 1") from error
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _bool(name: str, value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    value = str(value)
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _timezone(value: Any) -> str | None:
    timezone = str(value) if value is not None else None
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
    playwright_cdp_endpoint: str | None
    playwright_cdp_timeout_seconds: int | None
    runner_container_image: str | None
    allow_unsafe_local_execution: bool
    visual_diff_threshold: float | None
    visual_tolerance_percent: float | None
    scheduler_timezone: str | None
    n8n_mcp_url: str | None
    n8n_bearer_token: str | None
    n8n_model: str | None
    n8n_max_tokens: int | None
    n8n_temperature: float | None
    n8n_timeout_seconds: int | None
    n8n_discovery_agent_id: str | None
    n8n_repair_agent_id: str | None
    n8n_visual_agent_id: str | None
    backend_internal_url: str | None
    credential_encryption_key: str | None
    auto_repair_retries: int
    enable_n8n_generation: bool
    enable_n8n_repair: bool
    enable_n8n_visual: bool
    enable_local_repair: bool

    @classmethod
    def from_env(cls, config_path: Path | None = None) -> "Settings":
        config = load_application_config(config_path)
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
            product_name=_env_or_config("PRODUCT_NAME", config, "product", "name"),
            cors_origins=cors_origins,
            runner_timeout_seconds=_positive_int("RUNNER_TIMEOUT_SECONDS", _env_or_config("RUNNER_TIMEOUT_SECONDS", config, "runner", "timeoutSeconds")),
            playwright_cdp_endpoint=_optional_env("PLAYWRIGHT_CDP_ENDPOINT"),
            playwright_cdp_timeout_seconds=_positive_int("PLAYWRIGHT_CDP_TIMEOUT_SECONDS", _env_or_config("PLAYWRIGHT_CDP_TIMEOUT_SECONDS", config, "runner", "cdpTimeoutSeconds")),
            runner_container_image=_env_or_config("RUNNER_CONTAINER_IMAGE", config, "runner", "containerImage"),
            allow_unsafe_local_execution=_bool("ALLOW_UNSANDBOXED_EXECUTION", _optional_env("ALLOW_UNSANDBOXED_EXECUTION")),
            visual_diff_threshold=_fraction("VISUAL_DIFF_THRESHOLD", _env_or_config("VISUAL_DIFF_THRESHOLD", config, "visual", "diffThreshold")),
            visual_tolerance_percent=_fraction("VISUAL_TOLERANCE_PERCENT", _env_or_config("VISUAL_TOLERANCE_PERCENT", config, "visual", "tolerancePercent")),
            scheduler_timezone=_timezone(_env_or_config("SCHEDULER_TIMEZONE", config, "scheduler", "timezone")),
            n8n_mcp_url=_env_or_config("N8N_MCP_URL", config, "n8n", "mcpUrl"),
            n8n_bearer_token=_optional_env("N8N_BEARER_TOKEN"),
            n8n_model=_env_or_config("N8N_MODEL", config, "n8n", "model"),
            n8n_max_tokens=_positive_int("N8N_MAX_TOKENS", _env_or_config("N8N_MAX_TOKENS", config, "n8n", "maxTokens")),
            n8n_temperature=_fraction("N8N_TEMPERATURE", _env_or_config("N8N_TEMPERATURE", config, "n8n", "temperature")),
            n8n_timeout_seconds=_positive_int("N8N_TIMEOUT_SECONDS", _env_or_config("N8N_TIMEOUT_SECONDS", config, "n8n", "timeoutSeconds")),
            n8n_discovery_agent_id=_env_or_config("N8N_DISCOVERY_AGENT_ID", config, "n8n", "discoveryAgentId"),
            n8n_repair_agent_id=_env_or_config("N8N_REPAIR_AGENT_ID", config, "n8n", "repairAgentId"),
            n8n_visual_agent_id=_env_or_config("N8N_VISUAL_AGENT_ID", config, "n8n", "visualAgentId"),
            backend_internal_url=_env_or_config("BACKEND_INTERNAL_URL", config, "backend", "internalUrl"),
            credential_encryption_key=_optional_env("CREDENTIAL_ENCRYPTION_KEY"),
            auto_repair_retries=1,
            enable_n8n_generation=_bool("ENABLE_N8N_GENERATION", _env_or_config("ENABLE_N8N_GENERATION", config, "n8n", "generationEnabled")),
            enable_n8n_repair=_bool("ENABLE_N8N_REPAIR", _env_or_config("ENABLE_N8N_REPAIR", config, "n8n", "repairEnabled")),
            enable_n8n_visual=_bool("ENABLE_N8N_VISUAL", _env_or_config("ENABLE_N8N_VISUAL", config, "n8n", "visualEnabled")),
            enable_local_repair=_bool("ENABLE_LOCAL_REPAIR", _env_or_config("ENABLE_LOCAL_REPAIR", config, "n8n", "localRepairEnabled")),
        )

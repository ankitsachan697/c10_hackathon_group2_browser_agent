from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from ..artifact_store import ArtifactStore
from ..database import Database


@dataclass
class AppServices:
    database: Database
    orchestrator: Any
    scheduler: Any
    artifacts: ArtifactStore
    agents: Any
    credential_vault: Any = None
    generation: Any = None
    companions: Any = None
    relay: Any = None
    run_tasks: set[Any] = field(default_factory=set)


def services(request: Request) -> AppServices:
    return request.app.state.services


def ok(data=None, meta=None):
    return {"data": data, "error": None, "meta": meta or {}}


def error(code: str, message: str):
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}

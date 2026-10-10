from dataclasses import dataclass
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


def services(request: Request) -> AppServices:
    return request.app.state.services


def ok(data=None, meta=None):
    return {"data": data, "error": None, "meta": meta or {}}


def error(code: str, message: str):
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}

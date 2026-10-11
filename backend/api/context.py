from dataclasses import dataclass, field
from typing import Any
import asyncio

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

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


async def submit_background_run(svc, journey_id, trigger, **options):
    from ..repositories import RunRepository
    from ..event_store import EventStore
    created = asyncio.get_running_loop().create_future()
    def on_created(value):
        if not created.done(): created.set_result(value)
    async def execute():
        try:
            await svc.orchestrator.run_journey(journey_id, trigger, on_run_created=on_created, **options)
        except Exception as failure:
            if not created.done(): created.set_exception(failure)
            else:
                value = created.result()
                RunRepository(svc.database).update(value["id"], {"status": "NEEDS_ATTENTION", "final_decision": f"Run interrupted: {type(failure).__name__}"})
                EventStore(svc.database).append("run", value["id"], "system", "run.finished", {"status": "NEEDS_ATTENTION"})
    task = asyncio.create_task(execute())
    svc.run_tasks.add(task)
    task.add_done_callback(svc.run_tasks.discard)
    try:
        return JSONResponse(ok(await created), status_code=202)
    except KeyError:
        raise HTTPException(404, detail=error("NOT_FOUND", "Saved journey not found"))
    except Exception:
        raise HTTPException(409, detail=error("RUN_UNAVAILABLE", "A run is already active or the browser is unavailable"))

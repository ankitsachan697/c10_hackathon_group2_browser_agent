from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .context import AppServices, error, ok, services
from ..models import TriggerSource
from ..repositories import RunRepository


router = APIRouter(prefix="/runs", tags=["runs"])


class RerunRequest(BaseModel):
    mode: str = "current"


@router.get("")
def list_runs(svc: AppServices = Depends(services)):
    return ok(RunRepository(svc.database).list())


@router.get("/{run_id}")
def get_run(run_id: str, svc: AppServices = Depends(services)):
    value = RunRepository(svc.database).get(run_id)
    if not value:
        raise HTTPException(404, detail=error("NOT_FOUND", "Run not found"))
    with svc.database.connect() as connection:
        value["attempts"] = [dict(row) for row in connection.execute(
            "SELECT * FROM run_attempts WHERE run_id = ? ORDER BY attempt_number", (run_id,)
        )]
    value["artifacts"] = svc.artifacts.repository.list_for_run(run_id)
    return ok(value)


@router.post("/{run_id}/rerun")
async def rerun(run_id: str, payload: RerunRequest, svc: AppServices = Depends(services)):
    historic = RunRepository(svc.database).get(run_id)
    if not historic or not historic.get("journey_id"):
        raise HTTPException(404, detail=error("NOT_FOUND", "Run not found"))
    if payload.mode not in {"current", "snapshot"}:
        raise HTTPException(422, detail=error("INVALID_MODE", "Mode must be current or snapshot"))
    trigger = TriggerSource.RERUN_CURRENT if payload.mode == "current" else TriggerSource.RERUN_SNAPSHOT
    return ok(await svc.orchestrator.run_journey(historic["journey_id"], trigger, script_version=run_id if payload.mode == "snapshot" else None))


@router.delete("/{run_id}")
def delete_run(run_id: str, svc: AppServices = Depends(services)):
    svc.artifacts.trash_run(run_id)
    return ok({"deleted": RunRepository(svc.database).delete(run_id)})

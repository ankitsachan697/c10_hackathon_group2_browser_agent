from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .context import AppServices, error, ok, services
from ..repositories import ScheduleRepository


router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    journey_id: str | None = None
    project_id: str | None = None
    local_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezone: str
    enabled: bool = True


@router.get("")
def list_schedules(svc: AppServices = Depends(services)):
    return ok(ScheduleRepository(svc.database).list())


@router.post("", status_code=201)
def create_schedule(payload: ScheduleCreate, svc: AppServices = Depends(services)):
    if not payload.journey_id and not payload.project_id:
        raise HTTPException(422, detail=error("INVALID_SCOPE", "Journey or project is required"))
    return ok(svc.scheduler.create_daily(journey_id=payload.journey_id, project_id=payload.project_id, local_time=payload.local_time, timezone_name=payload.timezone, enabled=payload.enabled))


@router.post("/{schedule_id}/run")
async def run_schedule(schedule_id: str, svc: AppServices = Depends(services)):
    try:
        return ok(await svc.scheduler.run_now(schedule_id))
    except KeyError:
        raise HTTPException(404, detail=error("NOT_FOUND", "Schedule not found"))


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, svc: AppServices = Depends(services)):
    return ok({"deleted": svc.scheduler.delete(schedule_id)})

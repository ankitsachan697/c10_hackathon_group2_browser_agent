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


class ScheduleUpdate(BaseModel):
    local_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    timezone: str | None = None
    enabled: bool | None = None


def _validate_scope(payload: ScheduleCreate, svc: AppServices) -> None:
    if bool(payload.journey_id) == bool(payload.project_id):
        raise HTTPException(422, detail=error("INVALID_SCOPE", "Choose exactly one journey or project"))
    table, resource_id = ("journeys", payload.journey_id) if payload.journey_id else ("projects", payload.project_id)
    with svc.database.connect() as connection:
        exists = connection.execute(f"SELECT 1 FROM {table} WHERE id = ?", (resource_id,)).fetchone()
    if not exists:
        raise HTTPException(422, detail=error("INVALID_SCOPE", "Selected scope does not exist"))


@router.get("")
def list_schedules(svc: AppServices = Depends(services)):
    return ok(ScheduleRepository(svc.database).list())


@router.post("", status_code=201)
def create_schedule(payload: ScheduleCreate, svc: AppServices = Depends(services)):
    _validate_scope(payload, svc)
    try:
        value = svc.scheduler.create_daily(journey_id=payload.journey_id, project_id=payload.project_id, local_time=payload.local_time, timezone_name=payload.timezone, enabled=payload.enabled)
    except ValueError as exception:
        raise HTTPException(422, detail=error("INVALID_SCHEDULE", str(exception))) from exception
    return ok(value)


@router.patch("/{schedule_id}")
def update_schedule(schedule_id: str, payload: ScheduleUpdate, svc: AppServices = Depends(services)):
    try:
        return ok(svc.scheduler.update(schedule_id, payload.model_dump(exclude_none=True)))
    except KeyError as exception:
        raise HTTPException(404, detail=error("NOT_FOUND", "Schedule not found")) from exception
    except ValueError as exception:
        raise HTTPException(422, detail=error("INVALID_SCHEDULE", str(exception))) from exception


@router.post("/{schedule_id}/run")
async def run_schedule(schedule_id: str, svc: AppServices = Depends(services)):
    try:
        return ok(await svc.scheduler.run_now(schedule_id))
    except KeyError:
        raise HTTPException(404, detail=error("NOT_FOUND", "Schedule not found"))


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, svc: AppServices = Depends(services)):
    return ok({"deleted": svc.scheduler.delete(schedule_id)})

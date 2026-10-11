"""Generation operation status and durable activity feed."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .context import AppServices, error, ok, services
from ..event_store import EventStore
from ..cloud_jobs import CloudJobError


router = APIRouter(prefix="/operations", tags=["operations"])


class GenerationRequest(BaseModel):
    project_id: str
    name: str = Field(min_length=1)
    target_url: str = Field(min_length=1)
    objective: str = ""
    username: str | None = None
    password: str | None = None
    browser_mode: str = "headless"
    companion_id: str | None = None
    offline: bool = False


@router.post("/generations", status_code=202)
async def create_generation(payload: GenerationRequest, idempotency_key: str = Header(..., alias="Idempotency-Key"), svc: AppServices = Depends(services)):
    if not svc.generation:
        raise HTTPException(503, detail=error("GENERATION_UNAVAILABLE", "Generation service is unavailable"))
    try:
        operation = svc.generation.submit(payload.model_dump(), idempotency_key)
    except CloudJobError as failure:
        raise HTTPException(409, detail=error("CLOUD_JOB_UNAVAILABLE", str(failure))) from failure
    except ValueError as failure:
        raise HTTPException(422, detail=error("INVALID_GENERATION", str(failure))) from failure
    svc.generation.schedule(operation["id"])
    return ok(operation)


@router.get("/{operation_id}")
def get_operation(operation_id: str, svc: AppServices = Depends(services)):
    with svc.database.connect() as connection:
        row = connection.execute("SELECT * FROM generation_operations WHERE id=?", (operation_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail=error("NOT_FOUND", "Operation not found"))
    return ok({key: value for key, value in dict(row).items() if key != "request_json"})


@router.get("/{operation_id}/events")
def get_operation_events(operation_id: str, after_seq: int = Query(0, ge=0), svc: AppServices = Depends(services)):
    return ok(EventStore(svc.database).list_after("operation", operation_id, after_seq))

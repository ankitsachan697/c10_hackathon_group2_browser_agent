"""Generation operation status and durable activity feed."""

from fastapi import APIRouter, Depends, HTTPException, Query

from .context import AppServices, error, ok, services
from ..event_store import EventStore


router = APIRouter(prefix="/operations", tags=["operations"])


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

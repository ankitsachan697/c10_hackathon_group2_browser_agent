from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .context import AppServices, error, ok, services


router = APIRouter(tags=["system"])


@router.get("/overview")
def overview(svc: AppServices = Depends(services)):
    with svc.database.connect() as db:
        counts = {row[0]: row[1] for row in db.execute("SELECT status,count(*) FROM runs GROUP BY status")}
        projects = db.execute("SELECT count(*) FROM projects WHERE archived=0").fetchone()[0]
        journeys = db.execute("SELECT count(*) FROM journeys WHERE active=1").fetchone()[0]
        scheduled = db.execute("SELECT id,next_run,timezone FROM schedules WHERE enabled=1 AND next_run IS NOT NULL ORDER BY next_run LIMIT 1").fetchone()
    passed = counts.get("PASSED", 0) + counts.get("PASSED_AFTER_REPAIR", 0)
    attention = counts.get("FAILED", 0) + counts.get("NEEDS_ATTENTION", 0)
    completed = passed + attention
    return ok({"total_runs": sum(counts.values()), "completed_runs": completed,
               "pass_rate": round(passed / completed * 100, 1) if completed else None,
               "needs_attention": attention, "repaired_runs": counts.get("PASSED_AFTER_REPAIR", 0),
               "active_runs": sum(counts.get(status, 0) for status in ("QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING")),
               "projects": projects, "journeys": journeys, "next_schedule": dict(scheduled) if scheduled else None})


@router.get("/config/public")
def public_config(request: Request):
    settings = request.app.state.settings
    return ok({"product_name": settings.product_name, "scheduler_timezone": settings.scheduler_timezone})


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, svc: AppServices = Depends(services)):
    artifact = svc.artifacts.repository.get(artifact_id)
    if not artifact or artifact.get("deleted_at"):
        raise HTTPException(404, detail=error("NOT_FOUND", "Artifact not found"))
    try:
        path = svc.artifacts.resolve(artifact_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, detail=error("NOT_FOUND", "Artifact not found"))
    if not path.is_file():
        raise HTTPException(404, detail=error("NOT_FOUND", "Artifact not found"))
    return FileResponse(path, media_type=artifact.get("media_type"))

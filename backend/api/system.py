from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from .context import AppServices, error, ok, services


router = APIRouter(tags=["system"])


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

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from ..cloud_media import media_path, verify_artifact_capability

router = APIRouter(tags=["private media"])


@router.get("/media/{artifact_id}")
def read_media(artifact_id: str, token: str, request: Request):
    policy = request.app.state.cloud_policy
    if not verify_artifact_capability(artifact_id, policy.media_secret, token):
        raise HTTPException(403, detail="Artifact link expired or invalid; reopen it from Studio")
    store = request.app.state.services.artifacts
    artifact = store.repository.get(artifact_id)
    try:
        path = media_path(store.root, artifact)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, detail="Artifact is unavailable") from None
    return FileResponse(path, media_type=artifact.get("media_type"), headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"})

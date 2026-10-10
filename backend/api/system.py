from fastapi import APIRouter, Request

from .context import ok


router = APIRouter(tags=["system"])


@router.get("/config/public")
def public_config(request: Request):
    settings = request.app.state.settings
    return ok({"product_name": settings.product_name, "scheduler_timezone": settings.scheduler_timezone})

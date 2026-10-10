from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import companions, environments, journeys, operations, projects, runs, schedules, system


def build_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")
    for child in (projects.router, journeys.router, operations.router, runs.router, schedules.router, environments.router, companions.router, system.router):
        router.include_router(child)
    return router


def install_api(app: FastAPI) -> None:
    app.include_router(build_api_router())

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exception: HTTPException):
        detail = exception.detail
        if isinstance(detail, dict) and "error" in detail:
            return JSONResponse(detail, status_code=exception.status_code)
        return JSONResponse({"data": None, "error": {"code": "HTTP_ERROR", "message": str(detail)}, "meta": {}}, status_code=exception.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exception: RequestValidationError):
        return JSONResponse({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exception.errors()}, "meta": {}}, status_code=422)

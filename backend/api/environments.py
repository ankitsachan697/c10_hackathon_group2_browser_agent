from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .context import AppServices, ok, services
from ..repositories import EnvironmentRepository


router = APIRouter(prefix="/environments", tags=["environments"])


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1)
    base_url: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)


@router.get("")
def list_environments(svc: AppServices = Depends(services)):
    return ok(EnvironmentRepository(svc.database).list())


@router.post("", status_code=201)
def create_environment(payload: EnvironmentCreate, svc: AppServices = Depends(services)):
    return ok(EnvironmentRepository(svc.database).create(payload.model_dump()))

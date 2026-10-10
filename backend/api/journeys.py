from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from .context import AppServices, error, ok, services
from ..models import TriggerSource
from ..repositories import JourneyRepository, ProjectRepository


router = APIRouter(prefix="/journeys", tags=["journeys"])


class JourneyCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1)
    target_url: str = Field(min_length=1)
    objective: str = ""
    script: str = ""
    username: str | None = None
    password: str | None = None


class JourneyGenerate(JourneyCreate):
    script: str = ""


class JourneyCredentials(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _journey(repo, resource_id):
    value = repo.get(resource_id)
    if not value:
        raise HTTPException(404, detail=error("NOT_FOUND", "Journey not found"))
    return value


def _create_data(payload: JourneyCreate, svc: AppServices) -> dict:
    data = payload.model_dump(exclude={"username", "password"})
    if payload.username is None and payload.password is None:
        return data
    if not payload.username or not payload.password:
        raise HTTPException(422, detail=error("INVALID_CREDENTIALS", "Username and password must be supplied together"))
    if not svc.credential_vault:
        raise HTTPException(503, detail=error("CREDENTIAL_VAULT_UNAVAILABLE", "Credential encryption is not configured"))
    data["credential_ciphertext"] = svc.credential_vault.encrypt(payload.username, payload.password)
    return data


@router.get("")
def list_journeys(svc: AppServices = Depends(services)):
    return ok(JourneyRepository(svc.database).list())


@router.post("", status_code=201)
def create_journey(payload: JourneyCreate, svc: AppServices = Depends(services)):
    if not ProjectRepository(svc.database).get(payload.project_id):
        raise HTTPException(422, detail=error("INVALID_PROJECT", "Project not found"))
    return ok(JourneyRepository(svc.database).create(_create_data(payload, svc)))


@router.post("/generate", status_code=201)
def generate_journey(payload: JourneyGenerate, svc: AppServices = Depends(services)):
    has_auth = bool(payload.username and payload.password)
    generated = svc.agents.generate_flow_script(
        url=payload.target_url, task_objective=payload.objective, credentials_meta={"has_auth": has_auth}
    )
    data = _create_data(payload, svc)
    data["script"] = generated["python_script"]
    journey = JourneyRepository(svc.database).create(data)
    return ok({**journey, "discovered_steps": generated.get("discovered_steps", [])})


@router.get("/{journey_id}")
def get_journey(journey_id: str, svc: AppServices = Depends(services)):
    return ok(_journey(JourneyRepository(svc.database), journey_id))


@router.post("/{journey_id}/regenerate")
def regenerate(journey_id: str, svc: AppServices = Depends(services)):
    repo = JourneyRepository(svc.database)
    journey = _journey(repo, journey_id)
    generated = svc.agents.generate_flow_script(url=journey["target_url"], task_objective=journey["objective"], credentials_meta={"has_auth": journey["has_credentials"]})
    return ok(repo.update(journey_id, {"script": generated["python_script"]}))


@router.put("/{journey_id}/credentials")
def replace_credentials(journey_id: str, payload: JourneyCredentials, svc: AppServices = Depends(services)):
    repo = JourneyRepository(svc.database)
    _journey(repo, journey_id)
    if not svc.credential_vault:
        raise HTTPException(503, detail=error("CREDENTIAL_VAULT_UNAVAILABLE", "Credential encryption is not configured"))
    return ok(repo.set_credentials(journey_id, svc.credential_vault.encrypt(payload.username, payload.password)))


@router.post("/{journey_id}/run")
async def run_journey(journey_id: str, svc: AppServices = Depends(services)):
    _journey(JourneyRepository(svc.database), journey_id)
    return ok(await svc.orchestrator.run_journey(journey_id, TriggerSource.ON_DEMAND))


@router.delete("/{journey_id}")
def delete_journey(journey_id: str, svc: AppServices = Depends(services)):
    repo = JourneyRepository(svc.database)
    _journey(repo, journey_id)
    return ok({"deleted": repo.delete(journey_id)})

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from .context import AppServices, error, ok, services, submit_background_run
from ..models import TriggerSource
from ..repositories import JourneyRepository, ProjectRepository
from ..n8n_client import AgentError


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
    offline: bool = False


class JourneyCredentials(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class JourneyRunRequest(BaseModel):
    browser_mode: str = "headless"
    companion_id: str | None = None
    background: bool = False


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
    try:
        generated = svc.agents.generate_flow_script(
            url=payload.target_url, task_objective=payload.objective, credentials_meta={"has_auth": has_auth},
            offline=payload.offline,
        )
    except AgentError as failure:
        raise HTTPException(503 if failure.code in {"AGENT_NOT_CONFIGURED", "AGENT_UNAVAILABLE"} else 502,
                            detail=error(failure.code, str(failure))) from failure
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
    try:
        generated = svc.agents.generate_flow_script(url=journey["target_url"], task_objective=journey["objective"], credentials_meta={"has_auth": journey["has_credentials"]})
    except AgentError as failure:
        raise HTTPException(503 if failure.code in {"AGENT_NOT_CONFIGURED", "AGENT_UNAVAILABLE"} else 502,
                            detail=error(failure.code, str(failure))) from failure
    return ok(repo.update(journey_id, {"script": generated["python_script"]}))


@router.put("/{journey_id}/credentials")
def replace_credentials(journey_id: str, payload: JourneyCredentials, svc: AppServices = Depends(services)):
    repo = JourneyRepository(svc.database)
    _journey(repo, journey_id)
    if not svc.credential_vault:
        raise HTTPException(503, detail=error("CREDENTIAL_VAULT_UNAVAILABLE", "Credential encryption is not configured"))
    return ok(repo.set_credentials(journey_id, svc.credential_vault.encrypt(payload.username, payload.password)))


@router.post("/{journey_id}/run")
async def run_journey(journey_id: str, payload: JourneyRunRequest | None = None, svc: AppServices = Depends(services)):
    _journey(JourneyRepository(svc.database), journey_id)
    selected = payload or JourneyRunRequest()
    if selected.browser_mode not in {"headless", "headed"}:
        raise HTTPException(422, detail=error("INVALID_MODE", "Browser mode must be headless or headed"))
    options = {"headed": selected.browser_mode == "headed", "companion_id": selected.companion_id}
    if selected.background or getattr(svc.orchestrator, "cloud_jobs", None):
        return await submit_background_run(svc, journey_id, TriggerSource.ON_DEMAND, **options)
    return ok(await svc.orchestrator.run_journey(journey_id, TriggerSource.ON_DEMAND, **options))


@router.delete("/{journey_id}")
def delete_journey(journey_id: str, svc: AppServices = Depends(services)):
    repo = JourneyRepository(svc.database)
    _journey(repo, journey_id)
    return ok({"deleted": repo.delete(journey_id)})

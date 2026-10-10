from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .context import AppServices, error, ok, services
from ..models import TriggerSource
from ..repositories import ProjectRepository


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    environment_id: str | None = None
    tags: list[str] = Field(default_factory=list)


def _get_or_404(repository, resource_id):
    value = repository.get(resource_id)
    if not value:
        raise HTTPException(404, detail=error("NOT_FOUND", "Project not found"))
    return value


@router.get("")
def list_projects(search: str = "", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), svc: AppServices = Depends(services)):
    values = ProjectRepository(svc.database).list()
    if search:
        values = [item for item in values if search.lower() in item["name"].lower()]
    return ok(values[offset:offset + limit], {"total": len(values), "limit": limit, "offset": offset})


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, svc: AppServices = Depends(services)):
    return ok(ProjectRepository(svc.database).create(payload.model_dump()))


@router.get("/{project_id}")
def get_project(project_id: str, svc: AppServices = Depends(services)):
    return ok(_get_or_404(ProjectRepository(svc.database), project_id))


@router.get("/{project_id}/deletion-impact")
def deletion_impact(project_id: str, svc: AppServices = Depends(services)):
    _get_or_404(ProjectRepository(svc.database), project_id)
    with svc.database.connect() as connection:
        journeys = connection.execute("SELECT COUNT(*) FROM journeys WHERE project_id=?", (project_id,)).fetchone()[0]
        schedules = connection.execute("SELECT COUNT(*) FROM schedules WHERE project_id=? OR journey_id IN (SELECT id FROM journeys WHERE project_id=?)", (project_id, project_id)).fetchone()[0]
        runs = connection.execute("SELECT COUNT(*) FROM runs WHERE project_id=? OR journey_id IN (SELECT id FROM journeys WHERE project_id=?)", (project_id, project_id)).fetchone()[0]
        artifacts = connection.execute("SELECT COUNT(*) FROM artifacts WHERE run_id IN (SELECT id FROM runs WHERE project_id=? OR journey_id IN (SELECT id FROM journeys WHERE project_id=?))", (project_id, project_id)).fetchone()[0]
    return ok({"journeys": journeys, "schedules": schedules, "runs": runs, "artifacts": artifacts})


@router.post("/{project_id}/run")
async def run_project(project_id: str, svc: AppServices = Depends(services)):
    _get_or_404(ProjectRepository(svc.database), project_id)
    return ok(await svc.orchestrator.run_project(project_id, TriggerSource.PROJECT))


@router.delete("/{project_id}")
def delete_project(project_id: str, svc: AppServices = Depends(services)):
    _get_or_404(ProjectRepository(svc.database), project_id)
    with svc.database.connect() as connection:
        run_ids = [row[0] for row in connection.execute("SELECT id FROM runs WHERE project_id=? OR journey_id IN (SELECT id FROM journeys WHERE project_id=?)", (project_id, project_id))]
    for run_id in run_ids:
        svc.artifacts.trash_run(run_id)
    return ok({"deleted": ProjectRepository(svc.database).delete(project_id)})

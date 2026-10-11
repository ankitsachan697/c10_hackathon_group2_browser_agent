"""Isolated, synthetic browser targets served with the deployed backend."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict

from .context import AppServices, error, ok, services

router = APIRouter(tags=["demo-lab"])
ASSETS = Path(__file__).resolve().parent.parent / "demo_shop"


class ScenarioChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locator_revision: Literal[0, 1] | None = None
    visual_variant: bool | None = None
    checkout_failure: bool | None = None


def scenario(svc: AppServices, scenario_id: str):
    with svc.database.connect() as db:
        row = db.execute("SELECT * FROM demo_scenarios WHERE id=?", (scenario_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail=error("NOT_FOUND", "Demo scenario not found"))
    value = dict(row)
    value["visual_variant"] = bool(value["visual_variant"])
    value["checkout_failure"] = bool(value["checkout_failure"])
    value["target_path"] = f"/api/demo-shop/{scenario_id}"
    return value


@router.post("/demo-lab/scenarios", status_code=201)
def create_scenario(svc: AppServices = Depends(services)):
    scenario_id = uuid.uuid4().hex
    with svc.database.transaction() as db:
        db.execute("INSERT INTO demo_scenarios(id,created_at) VALUES (?,?)",
                   (scenario_id, datetime.now(timezone.utc).isoformat()))
    return ok(scenario(svc, scenario_id))


@router.get("/demo-lab/scenarios")
def list_scenarios(svc: AppServices = Depends(services)):
    with svc.database.connect() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM demo_scenarios ORDER BY created_at DESC LIMIT 50")]
    return ok([scenario(svc, item) for item in ids])


@router.patch("/demo-lab/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, change: ScenarioChange, svc: AppServices = Depends(services)):
    scenario(svc, scenario_id)
    values = change.model_dump(exclude_unset=True, exclude_none=True)
    if values:
        # All column names are taken from the explicit model, never client SQL.
        with svc.database.transaction() as db:
            db.execute(f"UPDATE demo_scenarios SET {','.join(f'{key}=?' for key in values)} WHERE id=?",
                       (*[int(value) for value in values.values()], scenario_id))
    return ok(scenario(svc, scenario_id))


@router.get("/demo-shop/assets/{filename}")
def demo_asset(filename: Literal["shop.css", "shop.js"]):
    return FileResponse(ASSETS / filename, headers={"Cache-Control": "no-store"})


@router.get("/demo-shop/{scenario_id}")
def demo_shop(scenario_id: str, svc: AppServices = Depends(services)):
    config = scenario(svc, scenario_id)
    # This JSON contains only switches, never submitted credentials/user content.
    html = (ASSETS / "index.html").read_text().replace("__SCENARIO_JSON__", json.dumps(config).replace("<", "\\u003c"))
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

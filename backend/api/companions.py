"""Operator-controlled pairing and non-secret companion availability."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .context import AppServices, error, ok, services
from ..companion_registry import CompanionError


router = APIRouter(prefix="/companions", tags=["companions"])


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=1)
    device_name: str = Field(min_length=1, max_length=100)


class HeartbeatRequest(BaseModel):
    device_id: str
    credential: str


def require_operator(svc: AppServices, token: str | None) -> None:
    if not svc.companions or not svc.companions.admin_token:
        raise HTTPException(503, detail=error("COMPANION_NOT_CONFIGURED", "Companion operator token is not configured"))
    if not token or not hmac.compare_digest(token, svc.companions.admin_token):
        raise HTTPException(403, detail=error("FORBIDDEN", "Operator authorization is required"))


@router.get("")
def list_companions(svc: AppServices = Depends(services)):
    return ok(svc.companions.list_online() if svc.companions else [])


@router.post("/pair-codes")
def issue_pair_code(x_companion_admin_token: str | None = Header(None), svc: AppServices = Depends(services)):
    require_operator(svc, x_companion_admin_token)
    return ok(svc.companions.issue_pair_code("default"))


@router.post("/exchange")
def exchange(payload: ExchangeRequest, svc: AppServices = Depends(services)):
    if not svc.companions:
        raise HTTPException(503, detail=error("COMPANION_NOT_CONFIGURED", "Pairing is unavailable"))
    try:
        return ok(svc.companions.exchange(payload.code, payload.device_name))
    except CompanionError as failure:
        raise HTTPException(422, detail=error("PAIRING_FAILED", str(failure))) from failure


@router.post("/heartbeat")
def heartbeat(payload: HeartbeatRequest, svc: AppServices = Depends(services)):
    if not svc.companions:
        raise HTTPException(503, detail=error("COMPANION_NOT_CONFIGURED", "Companion registry is unavailable"))
    try:
        svc.companions.heartbeat(payload.device_id, payload.credential)
        return ok({"online": True})
    except CompanionError as failure:
        raise HTTPException(403, detail=error("INVALID_DEVICE", str(failure))) from failure


@router.delete("/{device_id}")
def revoke(device_id: str, x_companion_admin_token: str | None = Header(None), svc: AppServices = Depends(services)):
    require_operator(svc, x_companion_admin_token)
    svc.companions.revoke(device_id)
    return ok({"revoked": True})

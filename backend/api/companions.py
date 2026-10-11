"""Operator-controlled pairing and non-secret companion availability."""

import hmac
import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket
from pydantic import BaseModel, Field

from .context import AppServices, error, ok, services
from ..companion_registry import CompanionError
from ..cdp_relay import RelayError


router = APIRouter(prefix="/companions", tags=["companions"])


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=1)
    device_name: str = Field(min_length=1, max_length=100)


class HeartbeatRequest(BaseModel):
    device_id: str


def require_operator(svc: AppServices, token: str | None) -> None:
    if not svc.companions or not svc.companions.admin_token:
        raise HTTPException(503, detail=error("COMPANION_NOT_CONFIGURED", "Companion operator token is not configured"))
    if not token or not hmac.compare_digest(token, svc.companions.admin_token):
        raise HTTPException(403, detail=error("FORBIDDEN", "Operator authorization is required"))


@router.get("")
def list_companions(svc: AppServices = Depends(services)):
    return ok(svc.companions.list_online() if svc.companions else [])


@router.get("/capabilities")
def browser_capabilities(svc: AppServices = Depends(services)):
    if getattr(getattr(svc.orchestrator, "runner", None), "requires_target_url", False):
        return ok({"location": "hosted", "headed_supported": False,
                   "reason": "Cloud headless is available. Remote headed pairing is not enabled in this release."})
    orchestrator = svc.orchestrator
    if not orchestrator:
        return ok({"location": "unavailable", "headed_supported": False, "reason": "Browser runner is unavailable"})
    if orchestrator.browser_location == "hosted":
        online = svc.companions.list_online() if svc.companions else []
        configured = bool(orchestrator.relay_base_url and svc.relay and svc.companions and svc.companions.admin_token)
        supported = configured and bool(online)
        return ok({"location": "hosted", "headed_supported": supported,
                   "reason": None if supported else "Pair and start a local browser companion first"})
    runner = orchestrator.runner
    supported = bool(getattr(runner, "cdp_endpoint", None) or
                     (not getattr(runner, "container_image", None) and getattr(runner, "allow_unsafe_local_execution", False)))
    return ok({"location": "local", "headed_supported": supported,
               "reason": None if supported else "Visible browser is unavailable in the isolated worker; use a paired local browser"})


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
def heartbeat(payload: HeartbeatRequest, authorization: str | None = Header(None), svc: AppServices = Depends(services)):
    if not svc.companions:
        raise HTTPException(503, detail=error("COMPANION_NOT_CONFIGURED", "Companion registry is unavailable"))
    try:
        svc.companions.heartbeat(payload.device_id, (authorization or "").removeprefix("Bearer "))
        return ok({"online": True})
    except CompanionError as failure:
        raise HTTPException(403, detail=error("INVALID_DEVICE", str(failure))) from failure


@router.get("/{device_id}/sessions")
def pending_sessions(device_id: str, authorization: str | None = Header(None), svc: AppServices = Depends(services)):
    try:
        svc.companions.authenticate(device_id, (authorization or "").removeprefix("Bearer "))
        return ok(svc.relay.pending_for(device_id) if svc.relay else [])
    except (CompanionError, AttributeError) as failure:
        raise HTTPException(403, detail=error("INVALID_DEVICE", "Companion authentication failed")) from failure


@router.websocket("/relay/{session_id}/companion")
async def companion_socket(websocket: WebSocket, session_id: str):
    svc = websocket.app.state.services
    device_id = websocket.headers.get("x-companion-device-id", "")
    credential = websocket.headers.get("authorization", "").removeprefix("Bearer ")
    try:
        svc.companions.authenticate(device_id, credential)
        await websocket.accept()
        await svc.relay.attach_companion(session_id, device_id, websocket)
    except (CompanionError, RelayError, AttributeError):
        await websocket.close(code=1008)


@router.websocket("/relay/{session_id}/runner")
async def runner_socket(websocket: WebSocket, session_id: str):
    svc = websocket.app.state.services
    secret = websocket.headers.get("authorization", "").removeprefix("Bearer ")
    try:
        await websocket.accept()
        await svc.relay.attach_runner(session_id, secret, websocket)
    except (RelayError, asyncio.TimeoutError, AttributeError):
        await websocket.close(code=1008)


@router.delete("/{device_id}")
def revoke(device_id: str, x_companion_admin_token: str | None = Header(None), svc: AppServices = Depends(services)):
    require_operator(svc, x_companion_admin_token)
    svc.companions.revoke(device_id)
    return ok({"revoked": True})

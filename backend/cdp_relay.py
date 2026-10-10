"""Ephemeral one-run CDP frame relay; control messages never contain scripts or secrets."""

from __future__ import annotations

import asyncio
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class RelayError(RuntimeError):
    pass


@dataclass
class RelaySession:
    id: str
    device_id: str
    run_id: str
    runner_secret: str
    expires_at: float
    companion: Any = None
    runner: Any = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)


class CdpRelay:
    def __init__(self, max_frame_bytes: int = 1024 * 1024):
        self.sessions: dict[str, RelaySession] = {}
        self.max_frame_bytes = max_frame_bytes

    def create_session(self, device_id: str, run_id: str, ttl_seconds: int = 90) -> RelaySession:
        if not device_id or not run_id or ttl_seconds <= 0:
            raise RelayError("Invalid relay session")
        if any(item.device_id == device_id and not item.closed.is_set() and item.expires_at > time.monotonic()
               for item in self.sessions.values()):
            raise RelayError("A browser session is already reserved on this device")
        session = RelaySession(f"relay_{uuid.uuid4().hex}", device_id, run_id,
                               secrets.token_urlsafe(32), time.monotonic() + ttl_seconds)
        self.sessions[session.id] = session
        return session

    def _get(self, session_id: str) -> RelaySession:
        session = self.sessions.get(session_id)
        if not session or session.closed.is_set() or session.expires_at <= time.monotonic():
            raise RelayError("Relay session is unavailable or expired")
        return session

    def control_message(self, session_id: str) -> dict[str, str]:
        session = self._get(session_id)
        return {"type": "session_offer", "session_id": session.id, "run_id": session.run_id}

    def pending_for(self, device_id: str) -> list[dict[str, str]]:
        return [self.control_message(item.id) for item in self.sessions.values()
                if item.device_id == device_id and not item.companion and not item.closed.is_set()
                and item.expires_at > time.monotonic()]

    async def attach_companion(self, session_id: str, device_id: str, websocket: Any) -> None:
        session = self._get(session_id)
        if session.device_id != device_id or session.companion is not None:
            raise RelayError("Companion is not authorized for this session")
        session.companion = websocket
        if session.runner:
            session.ready.set()
        await session.closed.wait()

    async def attach_runner(self, session_id: str, runner_secret: str, websocket: Any) -> None:
        session = self._get(session_id)
        if not runner_secret or not hmac.compare_digest(session.runner_secret, runner_secret) or session.runner is not None:
            raise RelayError("Runner is not authorized for this session")
        session.runner = websocket
        if session.companion:
            session.ready.set()
        try:
            await asyncio.wait_for(session.ready.wait(), timeout=max(0.1, session.expires_at - time.monotonic()))
            companion = session.companion
            if not companion:
                raise RelayError("Companion did not connect")
            tasks = [asyncio.create_task(self._forward(websocket, companion)),
                     asyncio.create_task(self._forward(companion, websocket))]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                if task.exception() is not None:
                    raise RelayError("CDP relay connection ended") from task.exception()
        finally:
            await self.close(session_id)

    async def _forward(self, source: Any, target: Any) -> None:
        while True:
            frame = await source.receive_text()
            if len(frame.encode("utf-8")) > self.max_frame_bytes:
                raise RelayError("CDP frame exceeds configured size")
            await target.send_text(frame)

    async def close(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if not session:
            return
        session.closed.set()
        for websocket in (session.companion, session.runner):
            if websocket:
                try:
                    await websocket.close()
                except Exception:
                    pass

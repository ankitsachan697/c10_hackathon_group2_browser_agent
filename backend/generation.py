"""Idempotent generation operation that starts one saved-script first run."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    from .database import Database
    from .event_store import EventStore
    from .models import TriggerSource
    from .n8n_client import AgentError
    from .repositories import JourneyRepository, ProjectRepository
    from .runner import validate_browser_script
except ImportError:
    from database import Database
    from event_store import EventStore
    from models import TriggerSource
    from n8n_client import AgentError
    from repositories import JourneyRepository, ProjectRepository
    from runner import validate_browser_script


class GenerationCoordinator:
    def __init__(self, database: Database, agents: Any, orchestrator: Any, credential_vault: Any, cloud_jobs=None):
        self.database = database
        self.agents = agents
        self.orchestrator = orchestrator
        self.credential_vault = credential_vault
        self.events = EventStore(database)
        self._tasks: set[asyncio.Task] = set()
        self.cloud_jobs = cloud_jobs

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM generation_operations WHERE id=?", (operation_id,)).fetchone()
        return {key: value for key, value in dict(row).items() if key != "request_json"} if row else None

    def submit(self, request: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("Idempotency-Key must be 1–200 characters")
        if request.get("browser_mode", "headless") not in {"headless", "headed"}:
            raise ValueError("browser_mode must be headless or headed")
        if request.get("companion_id") and request.get("browser_mode") != "headed":
            raise ValueError("companion_id requires headed browser mode")
        if not ProjectRepository(self.database).get(str(request.get("project_id", ""))):
            raise ValueError("Project not found")
        username, password = request.get("username"), request.get("password")
        if bool(username) != bool(password):
            raise ValueError("Username and password must be supplied together")
        with self.database.connect() as connection:
            existing = connection.execute("SELECT id FROM generation_operations WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            return self.get(existing["id"])
        payload = {key: value for key, value in request.items() if key not in {"username", "password"}}
        payload["has_auth"] = bool(username)
        if username and password:
            if self.credential_vault is None:
                raise ValueError("Credential vault is unavailable")
            payload["credential_ciphertext"] = self.credential_vault.encrypt(str(username), str(password))
        operation_id, now = f"gen_{uuid.uuid4().hex}", self._now()
        if self.cloud_jobs:
            self.cloud_jobs.reserve(operation_id)
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO generation_operations(id,idempotency_key,status,request_json,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                    (operation_id, idempotency_key, "QUEUED", json.dumps(payload), now, now),
                )
            self.events.append("operation", operation_id, "system", "generation.queued", {"name": payload.get("name", "")})
        except BaseException:
            if self.cloud_jobs: self.cloud_jobs.release(operation_id)
            raise
        return self.get(operation_id)

    def schedule(self, operation_id: str) -> None:
        task = asyncio.create_task(self.execute(operation_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def recover(self) -> None:
        if self.cloud_jobs:
            with self.database.transaction() as connection:
                connection.execute("UPDATE generation_operations SET status='FAILED',error_code='INTERRUPTED',error_message='Cloud session interrupted; review before submitting again',updated_at=? WHERE status IN ('QUEUED','RUNNING')", (self._now(),))
            self.cloud_jobs.active_job = None
            return
        with self.database.connect() as connection:
            queued = [row[0] for row in connection.execute("SELECT id FROM generation_operations WHERE status='QUEUED'")]
            connection.execute(
                "UPDATE generation_operations SET status='FAILED',error_code='INTERRUPTED',"
                "error_message='Generation was interrupted; submit again to retry',updated_at=? WHERE status='RUNNING'",
                (self._now(),),
            )
            connection.commit()
        for operation_id in queued:
            self.schedule(operation_id)

    async def execute(self, operation_id: str) -> None:
        if self.cloud_jobs:
            value = self.get(operation_id)
            if not value or value["status"] != "QUEUED":
                return
            try:
                async with self.cloud_jobs.job(operation_id, reserved=True):
                    return await self._execute(operation_id)
            except TimeoutError:
                with self.database.transaction() as connection:
                    connection.execute("UPDATE generation_operations SET status='FAILED',error_code='JOB_DEADLINE',error_message='Cloud job reached its ten-minute budget; review evidence before rerunning',updated_at=? WHERE id=?", (self._now(), operation_id))
                self.orchestrator.recover_interrupted()
                self.events.append("operation", operation_id, "system", "generation.failed", {"code": "JOB_DEADLINE"})
                return
        return await self._execute(operation_id)

    async def _execute(self, operation_id: str) -> None:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM generation_operations WHERE id=?", (operation_id,)).fetchone()
            if not row or row["status"] != "QUEUED":
                return
            connection.execute("UPDATE generation_operations SET status='RUNNING',updated_at=? WHERE id=?", (self._now(), operation_id))
            request = json.loads(row["request_json"])
        self.events.append("operation", operation_id, "agent", "generation.started", {"agent_id": getattr(self.agents.settings, "n8n_discovery_agent_id", None)} if hasattr(self.agents, "settings") else {})
        try:
            generated = await (self.cloud_jobs.run_sync if self.cloud_jobs else asyncio.to_thread)(
                self.agents.generate_flow_script,
                url=request["target_url"], task_objective=request.get("objective", ""),
                credentials_meta={"has_auth": request["has_auth"]}, offline=bool(request.get("offline", False)),
            )
            script = generated["python_script"]
            try:
                validate_browser_script(script)
            except (ValueError, SyntaxError) as failure:
                raise AgentError("AGENT_RESPONSE_INVALID", "Discovery agent returned an unsafe or invalid script") from failure
            journey = JourneyRepository(self.database).create({
                "project_id": request["project_id"], "name": request["name"], "target_url": request["target_url"],
                "objective": request.get("objective", ""), "script": script,
                "credential_ciphertext": request.get("credential_ciphertext"),
            })
            with self.database.transaction() as connection:
                connection.execute("UPDATE generation_operations SET journey_id=?,updated_at=? WHERE id=?", (journey["id"], self._now(), operation_id))
            self.events.append("operation", operation_id, "agent", "generation.completed", {
                "journey_id": journey["id"], "agent_id": generated.get("agent_id"),
                "agent_source": generated.get("agent_source"), "discovered_steps": generated.get("discovered_steps", []),
            })

            def on_run_created(run: dict[str, Any]) -> None:
                with self.database.transaction() as connection:
                    connection.execute("UPDATE generation_operations SET run_id=?,updated_at=? WHERE id=?", (run["id"], self._now(), operation_id))
                self.events.append("operation", operation_id, "system", "run.queued", {"run_id": run["id"]})

            await self.orchestrator.run_journey(
                journey["id"], TriggerSource.ON_DEMAND,
                headed=request.get("browser_mode") == "headed", on_run_created=on_run_created,
                companion_id=request.get("companion_id"),
            )
            with self.database.transaction() as connection:
                connection.execute("UPDATE generation_operations SET status='COMPLETED',updated_at=? WHERE id=?", (self._now(), operation_id))
            self.events.append("operation", operation_id, "system", "generation.finished", {})
        except Exception as failure:
            code = failure.code if isinstance(failure, AgentError) else "GENERATION_FAILED"
            message = str(failure) if isinstance(failure, AgentError) else "Journey generation or first execution failed"
            with self.database.transaction() as connection:
                connection.execute("UPDATE generation_operations SET status='FAILED',error_code=?,error_message=?,updated_at=? WHERE id=?",
                                   (code, message, self._now(), operation_id))
            self.events.append("operation", operation_id, "system", "generation.failed", {"code": code, "message": message})

"""One deterministic execution state machine for every operational trigger."""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .database import Database
    from .failure_context import build_failure_packet, classify_failure
    from .models import RunStatus, TriggerSource
    from .repositories import ArtifactRepository, JourneyRepository, RunRepository
    from .redaction import SensitiveDataRedactor
except ImportError:
    from database import Database
    from failure_context import build_failure_packet, classify_failure
    from models import RunStatus, TriggerSource
    from repositories import ArtifactRepository, JourneyRepository, RunRepository
    from redaction import SensitiveDataRedactor


class RunOverlapError(RuntimeError):
    pass


class RunOrchestrator:
    def __init__(self, database: Database, runner: Any, agents: Any, timeout_seconds: int, credential_vault: Any = None):
        self.database = database
        self.runner = runner
        self.agents = agents
        self.timeout_seconds = timeout_seconds
        self.journeys = JourneyRepository(database)
        self.runs = RunRepository(database)
        self.artifacts = ArtifactRepository(database)
        self.credential_vault = credential_vault
        self._active: set[str] = set()
        self._guard = asyncio.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record_attempt(self, run_id: str, attempt_number: int, result: dict[str, Any], secrets: Iterable[str] = ()) -> None:
        redactor = SensitiveDataRedactor(secrets)
        def redact(value: Any) -> str:
            return redactor.redact(str(value or ""))
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO run_attempts(id,run_id,attempt_number,status,stdout,stderr,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    f"att_{uuid.uuid4().hex}", run_id, attempt_number,
                    "PASSED" if result.get("passed") else "FAILED",
                    redact(result.get("stdout", ""))[:100_000],
                    redact(result.get("stderr", ""))[:100_000],
                    self._now(),
                ),
            )
        root_value = getattr(self.runner, "artifacts_dir", None)
        run_dir_value = result.get("run_dir")
        if not root_value or not run_dir_value:
            return
        root = Path(root_value).resolve()
        run_dir = Path(run_dir_value).resolve()
        if not run_dir.is_relative_to(root) or not run_dir.exists():
            return
        for path in run_dir.rglob("*"):
            if path.is_symlink():
                path.unlink(missing_ok=True)
                continue
            try:
                path.resolve().relative_to(run_dir)
            except (OSError, ValueError):
                continue
            if not path.is_file() or path.name == "test_script.py":
                continue
            if path.suffix.lower() in {".txt", ".log", ".html", ".htm", ".json"}:
                rendered = path.read_text(encoding="utf-8", errors="replace")
                path.write_text(redact(rendered), encoding="utf-8")
            relative = path.relative_to(root).as_posix()
            kind = (
                "screenshot" if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
                else "video" if path.suffix.lower() == ".webm"
                else "dom" if path.suffix.lower() in {".html", ".htm"}
                else "log"
            )
            self.artifacts.create({
                "run_id": run_id,
                "kind": kind,
                "storage_path": relative,
                "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "size_bytes": path.stat().st_size,
                "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
            })

    def _finish(self, run_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        return self.runs.update(run_id, {**changes, "finished_at": self._now()})

    async def _claim(self, scope: str) -> None:
        async with self._guard:
            if scope in self._active:
                raise RunOverlapError(f"A run is already active for {scope}")
            self._active.add(scope)

    async def run_journey(
        self,
        journey_id: str,
        trigger: TriggerSource | str,
        script_version: str | None = None,
        secrets: Iterable[str] = (),
        schedule_id: str | None = None,
        headed: bool = False,
        on_run_created: Any = None,
    ) -> dict[str, Any]:
        journey = self.journeys.get_with_credentials(journey_id)
        if not journey:
            raise KeyError(journey_id)
        scope = f"journey:{journey_id}"
        await self._claim(scope)
        try:
            trigger_value = trigger.value if isinstance(trigger, TriggerSource) else str(trigger)
            script, version = journey["script"], journey["script_version"]
            if trigger_value == TriggerSource.RERUN_SNAPSHOT.value and script_version:
                historic = self.runs.get(script_version)
                if not historic or historic.get("journey_id") != journey_id:
                    raise KeyError(script_version)
                script, version = historic["script_snapshot"], historic["script_version"]
            run = self.runs.create({
                "journey_id": journey_id, "project_id": journey["project_id"], "schedule_id": schedule_id,
                "trigger_source": trigger_value, "status": RunStatus.QUEUED.value,
                "script_snapshot": script, "script_version": version,
            })
            if on_run_created:
                on_run_created(run)
            env_vars: dict[str, str] = {}
            execution_secrets = list(secrets)
            if journey.get("credential_ciphertext"):
                if not self.credential_vault:
                    return self._finish(run["id"], {"status": RunStatus.NEEDS_ATTENTION.value, "final_decision": "Credential vault unavailable"})
                try:
                    username, password = self.credential_vault.decrypt(journey["credential_ciphertext"])
                except Exception:
                    return self._finish(run["id"], {"status": RunStatus.NEEDS_ATTENTION.value, "final_decision": "Credential decryption failed"})
                env_vars = {"AUTH_USERNAME": username, "AUTH_PASSWORD": password}
                execution_secrets.extend((username, password))
            self.runs.update(run["id"], {"status": RunStatus.RUNNING.value, "started_at": self._now()})
            try:
                first = await self.runner.execute_script(
                    script_code=script, timeout_seconds=self.timeout_seconds,
                    execution_id=f"{run['id']}/attempt-1",
                    env_vars=env_vars, secrets=execution_secrets,
                    headed=headed,
                )
            except Exception as error:
                return self._finish(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "final_decision": f"Execution worker failed: {type(error).__name__}",
                })
            self._record_attempt(run["id"], 1, first, execution_secrets)
            if first.get("passed"):
                return self._finish(run["id"], {"status": RunStatus.PASSED.value, "attempt_count": 1})

            decision = classify_failure(first)
            if not decision.eligible:
                return self._finish(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": decision.reason,
                })

            packet = replace(build_failure_packet(first, secrets=execution_secrets), original_script=script)
            self.runs.update(run["id"], {"status": RunStatus.DIAGNOSING.value})
            try:
                repair = self.agents.diagnose_and_repair(packet)
            except Exception as error:
                return self._finish(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": f"Repair service unavailable: {type(error).__name__}",
                })
            if not isinstance(repair, dict) or not isinstance(repair.get("repaired_script"), str) or not repair["repaired_script"].strip():
                return self._finish(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": "Repair response was invalid",
                })

            self.runs.update(run["id"], {
                "status": RunStatus.RETRYING.value,
                "diagnosis_json": json.dumps({key: value for key, value in repair.items() if key != "repaired_script"}),
                "repair_patch": repair["repaired_script"],
            })
            try:
                second = await self.runner.execute_script(
                    script_code=repair["repaired_script"], timeout_seconds=self.timeout_seconds,
                    execution_id=f"{run['id']}/attempt-2",
                    env_vars=env_vars, secrets=execution_secrets,
                    headed=headed,
                )
            except Exception as error:
                return self._finish(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": f"Repair retry worker failed: {type(error).__name__}",
                })
            self._record_attempt(run["id"], 2, second, execution_secrets)
            return self._finish(run["id"], {
                "status": (RunStatus.PASSED_AFTER_REPAIR.value if second.get("passed") else RunStatus.NEEDS_ATTENTION.value),
                "attempt_count": 2,
                "final_decision": "Verified repaired script" if second.get("passed") else "Automatic retry failed",
            })
        finally:
            async with self._guard:
                self._active.discard(scope)

    async def run_project(self, project_id: str, trigger: TriggerSource | str) -> list[dict[str, Any]]:
        results = []
        for journey in self.journeys.list_for_project(project_id):
            results.append(await self.run_journey(journey["id"], trigger))
        return results

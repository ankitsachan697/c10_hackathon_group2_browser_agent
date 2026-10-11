"""One deterministic execution state machine for every operational trigger."""

from __future__ import annotations

import asyncio
import ast
from collections import Counter
import hashlib
import json
import mimetypes
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Iterable

try:
    from .database import Database
    from .failure_context import build_failure_packet, classify_failure
    from .models import RunStatus, TriggerSource
    from .repositories import ArtifactRepository, JourneyRepository, RunRepository
    from .redaction import SensitiveDataRedactor
    from .event_store import EventStore
    from .runner import validate_browser_script
    from .visual_review import VisualReview
except ImportError:
    from database import Database
    from failure_context import build_failure_packet, classify_failure
    from models import RunStatus, TriggerSource
    from repositories import ArtifactRepository, JourneyRepository, RunRepository
    from redaction import SensitiveDataRedactor
    from event_store import EventStore
    from runner import validate_browser_script
    from visual_review import VisualReview


class RunOverlapError(RuntimeError):
    pass


def _expectations_preserved(original: str, repaired: str) -> bool:
    """Conservative guard: locator repair cannot remove or rewrite test assertions."""
    def assertions(script: str) -> Counter:
        return Counter(ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(script))
                       if isinstance(node, ast.Assert) or (
                           isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                           and node.func.attr.startswith(("to_be_", "to_have_", "to_contain_"))))
    return not (assertions(original) - assertions(repaired))


class RunOrchestrator:
    def __init__(self, database: Database, runner: Any, agents: Any, timeout_seconds: int, credential_vault: Any = None,
                 visual_review: VisualReview | None = None, browser_location: str = "local",
                 companion_registry: Any = None, cdp_relay: Any = None, relay_base_url: str | None = None):
        self.database = database
        self.runner = runner
        self.agents = agents
        self.timeout_seconds = timeout_seconds
        self.journeys = JourneyRepository(database)
        self.runs = RunRepository(database)
        self.artifacts = ArtifactRepository(database)
        self.credential_vault = credential_vault
        self.events = EventStore(database)
        self.visual_review = visual_review
        self.browser_location = browser_location
        self.companion_registry = companion_registry
        self.cdp_relay = cdp_relay
        self.relay_base_url = relay_base_url
        self._active: set[str] = set()
        self._guard = asyncio.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def recover_interrupted(self) -> int:
        """Startup-only recovery for the documented single-backend deployment.

        Never replay uncertain browser side effects after a process restart.
        Preserve attempts/evidence and make abandoned runs reviewable/deletable.
        """
        active = ("QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING")
        now = self._now()
        reason = "Backend restarted while this run was active; execution was interrupted. Review evidence before rerunning."
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM runs WHERE status IN (?,?,?,?,?)", active,
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE runs SET status=?,finished_at=?,final_decision=? WHERE id=?",
                    ("NEEDS_ATTENTION", now, reason, row["id"]),
                )
                for kind, payload in (
                    ("run.interrupted", {"reason": reason}),
                    ("run.finished", {"status": "NEEDS_ATTENTION", "interrupted": True}),
                ):
                    connection.execute(
                        "INSERT INTO activity_events(scope_type,scope_id,source,kind,payload_json,created_at) VALUES (?,?,?,?,?,?)",
                        ("run", row["id"], "system", kind, json.dumps(payload), now),
                    )
        return len(rows)

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
        result = self.runs.update(run_id, {**changes, "finished_at": self._now()})
        self.events.append("run", run_id, "system", "run.finished", {
            "status": result["status"], "attempt_count": result.get("attempt_count", 0),
        })
        return result

    def _record_agent_invocation(self, run_id: str, agent_id: str, status: str, duration_ms: int,
                                 error_code: str | None = None, usage: Any = None) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO agent_invocations(id,run_id,agent_id,purpose,status,duration_ms,usage_json,error_code,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (f"inv_{uuid.uuid4().hex}", run_id, agent_id, "repair", status, duration_ms,
                 json.dumps(usage) if isinstance(usage, dict) else None, error_code, self._now()),
            )

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
        companion_id: str | None = None,
        on_run_created: Any = None,
        event_sink: Any = None,
    ) -> dict[str, Any]:
        journey = self.journeys.get_with_credentials(journey_id)
        if not journey:
            raise KeyError(journey_id)
        scope = f"journey:{journey_id}"
        await self._claim(scope)
        relay_session_id: str | None = None
        try:
            trigger_value = trigger.value if isinstance(getattr(trigger, "value", None), str) else str(trigger)
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
            execution_secrets = list(secrets)

            def emit(source: str, kind: str, payload: dict[str, Any]) -> None:
                event = self.events.append("run", run["id"], source, kind, payload, secrets=execution_secrets)
                if event_sink:
                    event_sink(event)

            emit("system", "run.queued", {"trigger": trigger_value, "headed": headed})
            if on_run_created:
                on_run_created(run)
            browser_kwargs: dict[str, str] = {}
            if (headed and self.browser_location == "local" and hasattr(self.runner, "container_image")
                    and getattr(self.runner, "container_image", None) and not getattr(self.runner, "cdp_endpoint", None)):
                emit("system", "browser.unavailable", {"reason": "Visible Chromium is unavailable in the isolated container"})
                return self._finish(run["id"], {"status": RunStatus.NEEDS_ATTENTION.value,
                                                 "final_decision": "Use a paired local browser or a configured private CDP endpoint"})
            if headed and self.browser_location == "hosted":
                available = self.companion_registry.list_online() if self.companion_registry else []
                parsed = urlparse(self.relay_base_url or "")
                if (not companion_id or companion_id not in {item["id"] for item in available}
                        or not self.cdp_relay or parsed.scheme not in {"ws", "wss"} or not parsed.netloc
                        or (parsed.scheme == "ws" and parsed.hostname not in {"localhost", "127.0.0.1", "host.docker.internal"})):
                    emit("system", "browser.unavailable", {"reason": "No approved local browser is online or relay is not configured"})
                    return self._finish(run["id"], {"status": RunStatus.NEEDS_ATTENTION.value,
                                                     "final_decision": "Hosted headed run requires an online paired browser and relay"})
                try:
                    relay_session = self.cdp_relay.create_session(companion_id, run["id"])
                    relay_session_id = relay_session.id
                    emit("system", "browser.waiting_approval", {"device_id": companion_id})
                    await self.cdp_relay.wait_companion(relay_session.id)
                except Exception as error:
                    emit("system", "browser.unavailable", {"reason": type(error).__name__})
                    return self._finish(run["id"], {"status": RunStatus.NEEDS_ATTENTION.value,
                                                     "final_decision": "Local browser did not approve or connect"})
                browser_kwargs = {
                    "cdp_endpoint": f"{self.relay_base_url.rstrip('/')}/api/companions/relay/{relay_session.id}/runner",
                    "cdp_runner_secret": relay_session.runner_secret,
                }
                emit("system", "browser.connected", {"device_id": companion_id})
            else:
                emit("system", "browser.target", {"location": self.browser_location, "headed": headed})
            env_vars: dict[str, str] = {}
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
            emit("system", "run.started", {"attempt": 1})

            def on_log(log: dict[str, Any]) -> None:
                emit("playwright", "log", {"level": log.get("level", "INFO"), "message": str(log.get("message", ""))[:3000]})

            def on_action(action: dict[str, Any]) -> None:
                emit("playwright", f"action.{action['phase']}", {"action": action["action"], "attempt": 1})

            async def complete(result: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
                if self.visual_review:
                    emit("visual", "visual.started", {"attempt": changes.get("attempt_count", 1)})
                    try:
                        run_dir = Path(result.get("run_dir") or "")
                        screenshots = [str(run_dir / name) for name in result.get("screenshots", [])
                                       if isinstance(name, str) and Path(name).name == name]
                        visual = await asyncio.to_thread(
                            self.visual_review.review, journey_id, run["id"], screenshots,
                            passed=changes["status"] in {RunStatus.PASSED.value, RunStatus.PASSED_AFTER_REPAIR.value},
                        )
                    except Exception as error:
                        visual = {"status": "ERROR", "reason": type(error).__name__}
                    for path_key, kind, id_key in (("diff_path", "visual_diff", "diff_artifact_id"),
                                                  ("baseline_path", "visual_baseline", "baseline_artifact_id"),
                                                  ("candidate_path", "visual_current", "candidate_artifact_id")):
                        value = visual.pop(path_key, None)
                        if not value:
                            continue
                        visual_root = Path(self.visual_review.artifacts_dir).resolve()
                        diff = Path(value).resolve()
                        if diff.is_relative_to(visual_root) and diff.is_file():
                            artifact = self.artifacts.create({
                                "run_id": run["id"], "kind": kind,
                                "storage_path": diff.relative_to(visual_root).as_posix(),
                                "media_type": "image/png", "size_bytes": diff.stat().st_size,
                                "checksum": hashlib.sha256(diff.read_bytes()).hexdigest(),
                            })
                            visual[id_key] = artifact["id"]
                    with self.database.transaction() as connection:
                        connection.execute(
                            "INSERT OR REPLACE INTO visual_reviews(run_id,payload_json,created_at) VALUES (?,?,?)",
                            (run["id"], json.dumps(visual), self._now()),
                        )
                    changes["visual_outcome"] = visual["status"]
                    emit("visual", "visual.finished", {key: visual[key] for key in
                         ("status", "mismatch_percentage", "agent_status", "agent_id") if key in visual})
                return self._finish(run["id"], changes)

            try:
                first = await self.runner.execute_script(
                    script_code=script, timeout_seconds=self.timeout_seconds,
                    execution_id=f"{run['id']}/attempt-1",
                    env_vars=env_vars, secrets=execution_secrets,
                    headed=headed,
                    **browser_kwargs,
                    on_log=on_log, on_action=on_action,
                )
            except Exception as error:
                return self._finish(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "final_decision": f"Execution worker failed: {type(error).__name__}",
                })
            self._record_attempt(run["id"], 1, first, execution_secrets)
            emit("system", "run.attempt_finished", {"attempt": 1, "passed": bool(first.get("passed"))})
            if first.get("passed"):
                return await complete(first, {"status": RunStatus.PASSED.value, "attempt_count": 1})

            decision = classify_failure(first)
            if not decision.eligible:
                emit("system", "repair.skipped", {"category": decision.category, "reason": decision.reason})
                return await complete(first, {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": decision.reason,
                })

            packet = replace(
                build_failure_packet(first, secrets=execution_secrets),
                original_script=SensitiveDataRedactor(execution_secrets).redact(script)[:12000],
            )
            self.runs.update(run["id"], {"status": RunStatus.DIAGNOSING.value})
            configured_agent_id = str(getattr(getattr(self.agents, "settings", None), "n8n_repair_agent_id", None) or "repair-agent")
            emit("agent", "repair.started", {"agent_id": configured_agent_id, "category": decision.category})
            repair_started = time.monotonic()
            try:
                repair = await asyncio.to_thread(self.agents.diagnose_and_repair, packet)
            except Exception as error:
                error_code = str(getattr(error, "code", type(error).__name__))
                self._record_agent_invocation(run["id"], configured_agent_id, "FAILED", int((time.monotonic() - repair_started) * 1000), error_code)
                emit("agent", "repair.failed", {"agent_id": configured_agent_id, "category": decision.category, "error_code": error_code})
                return await complete(first, {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": f"Repair service unavailable: {type(error).__name__}",
                })
            if not isinstance(repair, dict) or not isinstance(repair.get("repaired_script"), str) or not repair["repaired_script"].strip():
                self._record_agent_invocation(run["id"], configured_agent_id, "FAILED", int((time.monotonic() - repair_started) * 1000), "AGENT_RESPONSE_INVALID")
                emit("agent", "repair.failed", {"agent_id": configured_agent_id, "category": decision.category, "error_code": "AGENT_RESPONSE_INVALID"})
                return await complete(first, {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": "Repair response was invalid",
                })
            try:
                validate_browser_script(repair["repaired_script"])
                if not _expectations_preserved(script, repair["repaired_script"]):
                    raise ValueError("Repair changed product expectations")
            except (ValueError, SyntaxError):
                self._record_agent_invocation(run["id"], configured_agent_id, "FAILED", int((time.monotonic() - repair_started) * 1000), "UNSAFE_REPAIR_SCRIPT")
                emit("agent", "repair.failed", {"agent_id": configured_agent_id, "category": decision.category, "error_code": "UNSAFE_REPAIR_SCRIPT"})
                return await complete(first, {"status": RunStatus.NEEDS_ATTENTION.value, "attempt_count": 1, "final_decision": "Repair script did not pass validation"})

            agent_id = str(repair.get("agent_id") or configured_agent_id)
            self._record_agent_invocation(run["id"], agent_id, "SUCCEEDED", int((time.monotonic() - repair_started) * 1000), usage=repair.get("usage"))
            emit("agent", "repair.finished", {"agent_id": agent_id, "category": decision.category,
                                                "source": str(repair.get("agent_source") or "n8n")[:120]})

            self.runs.update(run["id"], {
                "status": RunStatus.RETRYING.value,
                "diagnosis_json": SensitiveDataRedactor(execution_secrets).redact(json.dumps({key: value for key, value in repair.items() if key != "repaired_script"})),
                "repair_patch": repair["repaired_script"],
            })
            emit("system", "run.retry_started", {"attempt": 2})
            def on_retry_action(action: dict[str, Any]) -> None:
                emit("playwright", f"action.{action['phase']}", {"action": action["action"], "attempt": 2})
            try:
                second = await self.runner.execute_script(
                    script_code=repair["repaired_script"], timeout_seconds=self.timeout_seconds,
                    execution_id=f"{run['id']}/attempt-2",
                    env_vars=env_vars, secrets=execution_secrets,
                    headed=headed,
                    **browser_kwargs,
                    on_log=on_log, on_action=on_retry_action,
                )
            except Exception as error:
                return await complete(first, {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": f"Repair retry worker failed: {type(error).__name__}",
                })
            self._record_attempt(run["id"], 2, second, execution_secrets)
            emit("system", "run.attempt_finished", {"attempt": 2, "passed": bool(second.get("passed"))})
            if second.get("passed"):
                promoted = self.journeys.promote_verified_repair(journey_id, script, version, repair["repaired_script"])
                emit("system", "repair.saved" if promoted else "repair.save_skipped", {
                    "script_version": version + 1 if promoted else version,
                    "reason": "Verified retry" if promoted else "Saved journey changed since this version was captured",
                })
            return await complete(second, {
                "status": (RunStatus.PASSED_AFTER_REPAIR.value if second.get("passed") else RunStatus.NEEDS_ATTENTION.value),
                "attempt_count": 2,
                "final_decision": "Verified repaired script" if second.get("passed") else "Automatic retry failed",
            })
        finally:
            if relay_session_id and self.cdp_relay:
                await self.cdp_relay.close(relay_session_id)
            async with self._guard:
                self._active.discard(scope)

    async def run_project(self, project_id: str, trigger: TriggerSource | str) -> list[dict[str, Any]]:
        results = []
        for journey in self.journeys.list_for_project(project_id):
            results.append(await self.run_journey(journey["id"], trigger))
        return results

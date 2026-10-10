"""One deterministic execution state machine for every operational trigger."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Any, Iterable

try:
    from .database import Database
    from .failure_context import build_failure_packet, classify_failure
    from .models import RunStatus, TriggerSource
    from .repositories import JourneyRepository, RunRepository
except ImportError:
    from database import Database
    from failure_context import build_failure_packet, classify_failure
    from models import RunStatus, TriggerSource
    from repositories import JourneyRepository, RunRepository


class RunOverlapError(RuntimeError):
    pass


class RunOrchestrator:
    def __init__(self, database: Database, runner: Any, agents: Any, timeout_seconds: int):
        self.database = database
        self.runner = runner
        self.agents = agents
        self.timeout_seconds = timeout_seconds
        self.journeys = JourneyRepository(database)
        self.runs = RunRepository(database)
        self._active: set[str] = set()
        self._guard = asyncio.Lock()

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
    ) -> dict[str, Any]:
        journey = self.journeys.get(journey_id)
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
                "journey_id": journey_id,
                "project_id": journey["project_id"],
                "schedule_id": schedule_id,
                "trigger_source": trigger_value,
                "status": RunStatus.QUEUED.value,
                "script_snapshot": script,
                "script_version": version,
            })
            self.runs.update(run["id"], {"status": RunStatus.RUNNING.value})
            first = await self.runner.execute_script(script_code=script, timeout_seconds=self.timeout_seconds)
            if first.get("passed"):
                return self.runs.update(run["id"], {"status": RunStatus.PASSED.value, "attempt_count": 1})

            decision = classify_failure(first)
            if not decision.eligible:
                return self.runs.update(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": decision.reason,
                })

            packet = replace(build_failure_packet(first, secrets=secrets), original_script=script)
            self.runs.update(run["id"], {"status": RunStatus.DIAGNOSING.value})
            try:
                repair = self.agents.diagnose_and_repair(packet)
            except Exception as error:
                return self.runs.update(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": f"Repair service unavailable: {type(error).__name__}",
                })
            if not isinstance(repair, dict) or not isinstance(repair.get("repaired_script"), str) or not repair["repaired_script"].strip():
                return self.runs.update(run["id"], {
                    "status": RunStatus.NEEDS_ATTENTION.value,
                    "attempt_count": 1,
                    "final_decision": "Repair response was invalid",
                })

            self.runs.update(run["id"], {
                "status": RunStatus.RETRYING.value,
                "diagnosis_json": json.dumps({key: value for key, value in repair.items() if key != "repaired_script"}),
                "repair_patch": repair["repaired_script"],
            })
            second = await self.runner.execute_script(script_code=repair["repaired_script"], timeout_seconds=self.timeout_seconds)
            return self.runs.update(run["id"], {
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

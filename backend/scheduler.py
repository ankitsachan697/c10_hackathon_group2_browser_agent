"""Restart-safe daily scheduling backed by SQLite records."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from .database import Database
    from .models import TriggerSource
    from .repositories import ScheduleRepository
except ImportError:
    from database import Database
    from models import TriggerSource
    from repositories import ScheduleRepository


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Invalid timezone: {name}") from error


def _clock(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ValueError("local_time must use HH:MM") from error
    return parsed.replace(second=0, microsecond=0)


def next_run(schedule: dict, now: datetime) -> datetime:
    zone = _zone(schedule["timezone"])
    clock = _clock(schedule["local_time"])
    now_utc = now.astimezone(timezone.utc)
    local_now = now_utc.astimezone(zone)
    day = local_now.date()
    for offset in range(3):
        naive = datetime.combine(day + timedelta(days=offset), clock)
        local_candidate = naive.replace(tzinfo=zone)
        candidate_utc = local_candidate.astimezone(timezone.utc)
        roundtrip = candidate_utc.astimezone(zone)
        if (roundtrip.hour, roundtrip.minute) != (clock.hour, clock.minute):
            candidate_utc = roundtrip.astimezone(timezone.utc)
        if candidate_utc > now_utc:
            return candidate_utc
    raise ValueError("Unable to calculate next daily run")


class APSchedulerAdapter:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)

    def add_daily(self, schedule: dict, callback):
        clock = _clock(schedule["local_time"])
        self.scheduler.add_job(
            callback,
            CronTrigger(hour=clock.hour, minute=clock.minute, timezone=_zone(schedule["timezone"])),
            id=schedule["id"],
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    def remove(self, schedule_id: str):
        if self.scheduler.get_job(schedule_id):
            self.scheduler.remove_job(schedule_id)

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)


class ScheduleService:
    def __init__(self, database: Database, orchestrator, adapter=None):
        self.database = database
        self.repository = ScheduleRepository(database)
        self.orchestrator = orchestrator
        self.adapter = adapter or APSchedulerAdapter()
        self._running: set[str] = set()
        self._guard = asyncio.Lock()

    def _install(self, schedule: dict) -> None:
        async def callback():
            await self.run_now(schedule["id"])
        self.adapter.add_daily(schedule, callback)

    def create_daily(self, *, journey_id: str | None = None, project_id: str | None = None, local_time: str, timezone_name: str, enabled: bool = True):
        probe = {"local_time": local_time, "timezone": timezone_name}
        calculated = next_run(probe, datetime.now(timezone.utc))
        schedule = self.repository.create({
            "journey_id": journey_id, "project_id": project_id, "local_time": local_time,
            "timezone": timezone_name, "enabled": enabled, "next_run": calculated.isoformat(),
        })
        if enabled:
            self._install(schedule)
        return schedule

    def update(self, schedule_id: str, changes: dict):
        current = self.repository.get(schedule_id)
        if not current:
            raise KeyError(schedule_id)
        candidate = {**current, **changes}
        candidate["next_run"] = next_run(candidate, datetime.now(timezone.utc)).isoformat()
        updated = self.repository.update(schedule_id, {**changes, "next_run": candidate["next_run"]})
        self.adapter.remove(schedule_id)
        if updated["enabled"]:
            self._install(updated)
        return updated

    def delete(self, schedule_id: str) -> bool:
        self.adapter.remove(schedule_id)
        return self.repository.delete(schedule_id)

    async def run_now(self, schedule_id: str):
        schedule = self.repository.get(schedule_id)
        if not schedule:
            raise KeyError(schedule_id)
        async with self._guard:
            if schedule_id in self._running:
                return {"overlap": True, "schedule_id": schedule_id}
            self._running.add(schedule_id)
        try:
            if schedule.get("journey_id"):
                result = await self.orchestrator.run_journey(
                    schedule["journey_id"], TriggerSource.SCHEDULED, schedule_id=schedule_id
                )
            else:
                result = await self.orchestrator.run_project(schedule["project_id"], TriggerSource.SCHEDULED)
            self.repository.update(schedule_id, {
                "last_run": datetime.now(timezone.utc).isoformat(),
                "next_run": next_run(schedule, datetime.now(timezone.utc)).isoformat(),
            })
            return result
        finally:
            async with self._guard:
                self._running.discard(schedule_id)

    def restore_enabled(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        restored = 0
        for schedule in self.repository.list_enabled():
            future = next_run(schedule, now)
            self.repository.update(schedule["id"], {"next_run": future.isoformat()})
            self._install(self.repository.get(schedule["id"]))
            restored += 1
        return restored

    def start(self):
        self.restore_enabled()
        self.adapter.start()

    def shutdown(self):
        self.adapter.shutdown()

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.database import Database
from backend.repositories import JourneyRepository, ProjectRepository, ScheduleRepository
from backend.scheduler import ScheduleService, next_run


class FakeAdapter:
    def __init__(self):
        self.jobs = {}
        self.started = False

    def add_daily(self, schedule, callback):
        self.jobs[schedule["id"]] = (schedule, callback)

    def remove(self, schedule_id):
        self.jobs.pop(schedule_id, None)

    def start(self):
        self.started = True

    def shutdown(self):
        self.started = False


class BlockingOrchestrator:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def run_journey(self, *args, **kwargs):
        self.calls += 1
        if self.calls > 1:
            return {"overlap": True}
        self.started.set()
        await self.release.wait()
        return {"status": "PASSED"}


@pytest.fixture
def service(tmp_path: Path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    project = ProjectRepository(database).create({"name": "Web"})
    journey = JourneyRepository(database).create({"project_id": project["id"], "name": "Flow", "target_url": "https://app.invalid", "script": "pass"})
    adapter = FakeAdapter()
    return ScheduleService(database, BlockingOrchestrator(), adapter), journey, adapter


def test_next_run_respects_asia_kolkata():
    now = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)
    calculated = next_run({"local_time": "09:30", "timezone": "Asia/Kolkata"}, now)
    assert calculated == datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc)


def test_next_run_handles_dst_gap_by_choosing_next_valid_time():
    now = datetime(2026, 3, 8, 5, 0, tzinfo=timezone.utc)
    calculated = next_run({"local_time": "02:30", "timezone": "America/New_York"}, now)
    assert calculated > now
    assert calculated.astimezone(timezone.utc).date() >= now.date()


def test_invalid_timezone_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        next_run({"local_time": "09:00", "timezone": "Mars/Olympus"}, datetime.now(timezone.utc))


def test_create_update_disable_and_restore(service):
    scheduler, journey, adapter = service
    created = scheduler.create_daily(journey_id=journey["id"], local_time="09:30", timezone_name="Asia/Kolkata")
    assert created["id"] in adapter.jobs

    disabled = scheduler.update(created["id"], {"enabled": False})
    assert disabled["enabled"] == 0
    assert created["id"] not in adapter.jobs

    scheduler.update(created["id"], {"enabled": True})
    restored = scheduler.restore_enabled(datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert restored == 1
    assert created["id"] in adapter.jobs


def test_restore_reconciles_missed_next_run_to_future(service):
    scheduler, journey, _ = service
    created = scheduler.create_daily(journey_id=journey["id"], local_time="09:30", timezone_name="Asia/Kolkata")
    ScheduleRepository(scheduler.database).update(created["id"], {"next_run": "2020-01-01T00:00:00+00:00"})
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    scheduler.restore_enabled(now)
    assert datetime.fromisoformat(ScheduleRepository(scheduler.database).get(created["id"])["next_run"]) > now


@pytest.mark.asyncio
async def test_schedule_and_run_now_overlap_returns_explicit_result(service):
    scheduler, journey, _ = service
    created = scheduler.create_daily(journey_id=journey["id"], local_time="09:30", timezone_name="Asia/Kolkata")
    first = asyncio.create_task(scheduler.run_now(created["id"]))
    await scheduler.orchestrator.started.wait()
    second = await scheduler.run_now(created["id"])
    scheduler.orchestrator.release.set()
    await first
    assert second == {"overlap": True, "schedule_id": created["id"]}

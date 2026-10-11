import asyncio
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.cloud_jobs import CloudJobs, CloudJobError
from backend.database import Database
from backend.generation import GenerationCoordinator
from backend.repositories import ProjectRepository


def make_jobs(monkeypatch):
    monkeypatch.setenv("CLOUD_SESSION_EXPIRES_AT", (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat())
    return CloudJobs(SimpleNamespace(sdk_credentials=lambda **kw: {"scoped": True}))


@pytest.mark.asyncio
async def test_one_cloud_job_is_admitted(monkeypatch):
    jobs = make_jobs(monkeypatch)
    async with jobs.job("one"):
        async with jobs.job("nested-saved-script"):
            assert jobs.active_job == "one"
        # A separate request/task must not inherit the in-progress job.
        import contextvars
        async def separate():
            with pytest.raises(CloudJobError, match="active"):
                async with jobs.job("two"):
                    pytest.fail("Second job admitted")
        await asyncio.create_task(separate(), context=contextvars.Context())
    assert jobs.active_job is None


def test_job_rejected_without_ten_minute_session_budget(monkeypatch):
    jobs = make_jobs(monkeypatch)
    monkeypatch.setenv("CLOUD_SESSION_EXPIRES_AT", (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
    with pytest.raises(CloudJobError, match="budget"):
        jobs.reserve("short")
    assert jobs.active_job is None


def test_interrupted_queued_generation_is_not_replayed_in_cloud(tmp_path, monkeypatch):
    db = Database(tmp_path / "app.db")
    db.initialize()
    project = ProjectRepository(db).create({"name": "Recovery proof"})
    jobs = make_jobs(monkeypatch)
    coordinator = GenerationCoordinator(db, None, None, None, cloud_jobs=jobs)
    request = {"project_id": project["id"], "name": "Proof", "target_url": "https://example.com/"}
    operation = coordinator.submit(request, "one")
    assert coordinator.submit(request, "one")["id"] == operation["id"]
    coordinator.schedule = lambda value: pytest.fail("Uncertain browser effects replayed")
    coordinator.recover()
    value = coordinator.get(operation["id"])
    assert value["status"] == "FAILED" and value["error_code"] == "INTERRUPTED"
    assert jobs.active_job is None


@pytest.mark.asyncio
async def test_cloud_job_deadline_releases_admission(monkeypatch):
    jobs = make_jobs(monkeypatch)
    jobs.job_seconds = 0.01
    with pytest.raises(TimeoutError):
        async with jobs.job("deadline"):
            await asyncio.sleep(0.1)
    assert jobs.active_job is None
@pytest.mark.asyncio
async def test_deadline_retains_admission_until_owned_thread_has_stopped(monkeypatch):
    monkeypatch.setenv("CLOUD_SESSION_EXPIRES_AT", (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
    jobs = make_jobs(monkeypatch)
    jobs.job_seconds = .01
    finished = []
    def stage():
        time.sleep(.05)
        finished.append(True)
    async def first():
        async with jobs.job("first"):
            await jobs.run_sync(stage)
    task = asyncio.create_task(first())
    await asyncio.sleep(.02)
    with pytest.raises(CloudJobError, match="active"):
        jobs.reserve("second")
    with pytest.raises(TimeoutError):
        await task
    assert finished == [True]
    assert jobs.active_job is None

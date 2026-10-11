"""Single-job admission and a shared deadline across discovery/repair/retry."""
import asyncio
import contextvars
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

_deadline = contextvars.ContextVar("studio_worker_deadline", default=None)


def remaining_job_seconds(default):
    deadline = _deadline.get()
    return default if deadline is None else min(default, max(0, int(deadline - time.monotonic())))


class CloudJobError(RuntimeError):
    pass


class CloudJobs:
    def __init__(self, policy, job_seconds=600):
        self.policy, self.job_seconds = policy, job_seconds
        self.active_job = None
        self._lock = threading.Lock()
        self._context = contextvars.ContextVar("studio_cloud_job", default=None)
        self._stages = set()

    async def run_sync(self, function, *args, **kwargs):
        """Cancellation must not orphan a thread that owns a worker or writes."""
        task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
        self._stages.add(task)
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self._stages.discard(task)

    def reserve(self, job_id):
        with self._lock:
            if self.active_job:
                raise CloudJobError("Another cloud browser job is active; wait for it to finish")
            try:
                expires = datetime.fromisoformat(os.environ["CLOUD_SESSION_EXPIRES_AT"].replace("Z", "+00:00")).timestamp()
                if expires < time.time() + self.job_seconds + 30:
                    raise ValueError("short session")
                self.policy.sdk_credentials(minimum_lifetime=self.job_seconds + 30)
            except (ValueError, KeyError):
                raise CloudJobError("Cloud session has insufficient ten-minute job budget; refresh after the session restarts") from None
            self.active_job = job_id

    def release(self, job_id):
        with self._lock:
            if self.active_job == job_id:
                self.active_job = None

    @asynccontextmanager
    async def job(self, job_id, reserved=False):
        if self._context.get() == self.active_job and self.active_job is not None:
            yield
            return
        if not reserved:
            self.reserve(job_id)
        elif self.active_job != job_id:
            raise CloudJobError("Cloud job reservation is no longer active")
        token = self._context.set(job_id)
        deadline_token = _deadline.set(time.monotonic() + self.job_seconds)
        try:
            async with asyncio.timeout(self.job_seconds):
                yield
        finally:
            # Keep admission closed during bounded provider/thread cleanup.
            # Recovery runs only after no stage can mutate the previous job.
            if self._stages:
                await asyncio.shield(asyncio.gather(*self._stages, return_exceptions=True))
                self._stages.clear()
            _deadline.reset(deadline_token)
            self._context.reset(token)
            self.release(job_id)

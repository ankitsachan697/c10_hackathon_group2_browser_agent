"""Focused SQLite repositories for browser automation resources."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    from .database import Database
except ImportError:
    from database import Database


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row):
    return dict(row) if row else None


class _Repository:
    table = ""

    def __init__(self, database: Database):
        self.database = database

    def get(self, resource_id: str):
        with self.database.connect() as connection:
            return _row(connection.execute(f"SELECT * FROM {self.table} WHERE id = ?", (resource_id,)).fetchone())

    def list(self):
        with self.database.connect() as connection:
            return [_row(row) for row in connection.execute(f"SELECT * FROM {self.table} ORDER BY created_at DESC")]

    def delete(self, resource_id: str) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(f"DELETE FROM {self.table} WHERE id = ?", (resource_id,))
            return cursor.rowcount > 0


class EnvironmentRepository(_Repository):
    table = "environments"

    def create(self, data: dict[str, Any]):
        resource_id, now = data.get("id") or _id("env"), _now()
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO environments(id,name,base_url,variables_json,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (resource_id, data["name"], data.get("base_url"), json.dumps(data.get("variables", {})), now, now),
            )
        return self.get(resource_id)


class ProjectRepository(_Repository):
    table = "projects"

    def create(self, data: dict[str, Any]):
        resource_id, now = data.get("id") or _id("prj"), _now()
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO projects(id,name,description,environment_id,tags_json,archived,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (resource_id, data["name"], data.get("description", ""), data.get("environment_id"), json.dumps(data.get("tags", [])), int(data.get("archived", False)), now, now),
            )
        return self.get(resource_id)

    def find_by_name(self, name: str):
        with self.database.connect() as connection:
            return _row(connection.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone())


class JourneyRepository(_Repository):
    table = "journeys"

    def create(self, data: dict[str, Any]):
        resource_id, now = data.get("id") or _id("jrn"), _now()
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO journeys(id,project_id,name,objective,target_url,script,script_version,active,browser_json,visual_threshold,baseline_state,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (resource_id, data["project_id"], data["name"], data.get("objective", ""), data["target_url"], data.get("script", ""), data.get("script_version", 1), int(data.get("active", True)), json.dumps(data.get("browser", {})), data.get("visual_threshold"), data.get("baseline_state"), now, now),
            )
        return self.get(resource_id)

    def update(self, resource_id: str, changes: dict[str, Any]):
        current = self.get(resource_id)
        if not current:
            return None
        allowed = {"name", "objective", "target_url", "script", "active", "visual_threshold", "baseline_state"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        if "script" in updates and updates["script"] != current["script"]:
            updates["script_version"] = current["script_version"] + 1
        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self.database.transaction() as connection:
            connection.execute(f"UPDATE journeys SET {assignments} WHERE id = ?", (*updates.values(), resource_id))
        return self.get(resource_id)


class ScheduleRepository(_Repository):
    table = "schedules"

    def create(self, data: dict[str, Any]):
        resource_id, now = data.get("id") or _id("sch"), _now()
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO schedules(id,journey_id,project_id,local_time,timezone,enabled,overlap_policy,next_run,last_run,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (resource_id, data.get("journey_id"), data.get("project_id"), data["local_time"], data["timezone"], int(data.get("enabled", True)), data.get("overlap_policy", "SKIP"), data.get("next_run"), data.get("last_run"), now, now),
            )
        return self.get(resource_id)


class RunRepository(_Repository):
    table = "runs"

    def create(self, data: dict[str, Any]):
        resource_id, now = data.get("id") or _id("run"), _now()
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO runs(id,journey_id,project_id,schedule_id,trigger_source,status,script_snapshot,script_version,attempt_count,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (resource_id, data.get("journey_id"), data.get("project_id"), data.get("schedule_id"), data.get("trigger_source", "ON_DEMAND"), data["status"], data.get("script_snapshot", ""), data.get("script_version", 1), data.get("attempt_count", 0), now),
            )
        return self.get(resource_id)

    def update(self, resource_id: str, changes: dict[str, Any]):
        immutable = {"id", "script_snapshot", "script_version", "created_at"}
        updates = {key: value for key, value in changes.items() if key not in immutable}
        if not updates or not self.get(resource_id):
            return self.get(resource_id)
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self.database.transaction() as connection:
            connection.execute(f"UPDATE runs SET {assignments} WHERE id = ?", (*updates.values(), resource_id))
        return self.get(resource_id)


class ArtifactRepository(_Repository):
    table = "artifacts"

    def create(self, data: dict[str, Any]):
        resource_id, now = data.get("id") or _id("art"), _now()
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO artifacts(id,run_id,kind,storage_path,media_type,size_bytes,checksum,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (resource_id, data["run_id"], data["kind"], data["storage_path"], data.get("media_type"), data.get("size_bytes"), data.get("checksum"), now),
            )
        return self.get(resource_id)

    def list_for_run(self, run_id: str):
        with self.database.connect() as connection:
            return [_row(row) for row in connection.execute("SELECT * FROM artifacts WHERE run_id = ?", (run_id,))]

    def mark_deleted(self, resource_id: str, deleted_at: str):
        with self.database.transaction() as connection:
            connection.execute("UPDATE artifacts SET deleted_at = ? WHERE id = ?", (deleted_at, resource_id))
        return self.get(resource_id)

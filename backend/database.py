"""SQLite connection and schema management."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', '1');
CREATE TABLE IF NOT EXISTS environments (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, base_url TEXT, variables_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', environment_id TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]', archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(environment_id) REFERENCES environments(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS journeys (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, objective TEXT NOT NULL DEFAULT '',
  target_url TEXT NOT NULL, script TEXT NOT NULL, script_version INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1, browser_json TEXT NOT NULL DEFAULT '{}', visual_threshold REAL,
  baseline_state TEXT, credential_ciphertext TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS schedules (
  id TEXT PRIMARY KEY, journey_id TEXT, project_id TEXT, local_time TEXT NOT NULL, timezone TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1, overlap_policy TEXT NOT NULL DEFAULT 'SKIP', next_run TEXT, last_run TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  CHECK (journey_id IS NOT NULL OR project_id IS NOT NULL),
  FOREIGN KEY(journey_id) REFERENCES journeys(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, journey_id TEXT, project_id TEXT, schedule_id TEXT, trigger_source TEXT NOT NULL DEFAULT 'ON_DEMAND',
  status TEXT NOT NULL, script_snapshot TEXT NOT NULL DEFAULT '', script_version INTEGER NOT NULL DEFAULT 1,
  attempt_count INTEGER NOT NULL DEFAULT 0, diagnosis_json TEXT, repair_patch TEXT, final_decision TEXT,
  visual_outcome TEXT, started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(journey_id) REFERENCES journeys(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS run_attempts (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, attempt_number INTEGER NOT NULL, status TEXT NOT NULL,
  stdout TEXT, stderr TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE,
  UNIQUE(run_id, attempt_number)
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, storage_path TEXT NOT NULL, media_type TEXT,
  size_bytes INTEGER, checksum TEXT, deleted_at TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS import_markers (
  source_key TEXT NOT NULL, legacy_id TEXT NOT NULL, imported_id TEXT NOT NULL,
  PRIMARY KEY(source_key, legacy_id)
);
CREATE TABLE IF NOT EXISTS generation_operations (
  id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
  request_json TEXT NOT NULL, journey_id TEXT, run_id TEXT, error_code TEXT, error_message TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, scope_type TEXT NOT NULL, scope_id TEXT NOT NULL,
  source TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS activity_events_scope ON activity_events(scope_type,scope_id,seq);
CREATE TABLE IF NOT EXISTS agent_invocations (
  id TEXT PRIMARY KEY, operation_id TEXT, run_id TEXT, agent_id TEXT NOT NULL,
  purpose TEXT NOT NULL, status TEXT NOT NULL, duration_ms INTEGER, usage_json TEXT,
  error_code TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visual_reviews (
  run_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS companion_pair_codes (
  code_hash TEXT PRIMARY KEY, user_scope TEXT NOT NULL, expires_at TEXT NOT NULL,
  used_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS companions (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, user_scope TEXT NOT NULL,
  credential_hash TEXT NOT NULL, last_seen TEXT, revoked_at TEXT, created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            journey_columns = {row[1] for row in connection.execute("PRAGMA table_info(journeys)")}
            if "credential_ciphertext" not in journey_columns:
                connection.execute("ALTER TABLE journeys ADD COLUMN credential_ciphertext TEXT")
            connection.execute(
                "INSERT INTO schema_meta(key,value) VALUES ('schema_version','5') "
                "ON CONFLICT(key) DO UPDATE SET value='5'"
            )
            schedule_fk = next(
                (row for row in connection.execute("PRAGMA foreign_key_list(runs)") if row[3] == "schedule_id"),
                None,
            )
        if schedule_fk and str(schedule_fk[6]).upper() != "SET NULL":
            self._migrate_schedule_history_fk()

    def _migrate_schedule_history_fk(self) -> None:
        """Preserve historical runs when an existing schedule is removed."""
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript(
                """
                BEGIN;
                CREATE TABLE runs_v2 (
                  id TEXT PRIMARY KEY, journey_id TEXT, project_id TEXT, schedule_id TEXT,
                  trigger_source TEXT NOT NULL DEFAULT 'ON_DEMAND', status TEXT NOT NULL,
                  script_snapshot TEXT NOT NULL DEFAULT '', script_version INTEGER NOT NULL DEFAULT 1,
                  attempt_count INTEGER NOT NULL DEFAULT 0, diagnosis_json TEXT, repair_patch TEXT,
                  final_decision TEXT, visual_outcome TEXT, started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL,
                  FOREIGN KEY(journey_id) REFERENCES journeys(id) ON DELETE CASCADE,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                  FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE SET NULL
                );
                INSERT INTO runs_v2 SELECT * FROM runs;
                DROP TABLE runs;
                ALTER TABLE runs_v2 RENAME TO runs;
                COMMIT;
                """
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

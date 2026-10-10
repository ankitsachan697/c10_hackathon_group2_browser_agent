"""Durable, bounded, redacted activity events for operations and runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from .database import Database
from .redaction import SensitiveDataRedactor


class EventStore:
    def __init__(self, database: Database):
        self.database = database

    def append(
        self, scope_type: str, scope_id: str, source: str, kind: str,
        payload: dict[str, Any], secrets: Iterable[str] = (),
    ) -> dict[str, Any]:
        if scope_type not in {"run", "operation"} or not scope_id or not source or not kind:
            raise ValueError("Invalid activity scope or event type")
        redactor = SensitiveDataRedactor(secrets)

        def clean(value: Any) -> Any:
            if isinstance(value, str):
                return redactor.redact(value)
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items()}
            if isinstance(value, list):
                return [clean(item) for item in value]
            return value

        sanitized = json.dumps(clean(payload), separators=(",", ":"))
        if len(sanitized.encode("utf-8")) > 4096:
            raise ValueError("Activity payload exceeds 4 KiB")
        clean_payload = json.loads(sanitized)
        created_at = datetime.now(timezone.utc).isoformat()
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO activity_events(scope_type,scope_id,source,kind,payload_json,created_at) VALUES (?,?,?,?,?,?)",
                (scope_type, scope_id, source, kind, sanitized, created_at),
            )
            sequence = cursor.lastrowid
        return {"seq": sequence, "scope_type": scope_type, "scope_id": scope_id,
                "source": source, "kind": kind, "payload": clean_payload, "created_at": created_at}

    def list_after(self, scope_type: str, scope_id: str, after_seq: int, limit: int = 200) -> list[dict[str, Any]]:
        if after_seq < 0:
            raise ValueError("after_seq must be non-negative")
        bounded_limit = max(1, min(limit, 200))
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM activity_events WHERE scope_type=? AND scope_id=? AND seq>? ORDER BY seq LIMIT ?",
                (scope_type, scope_id, after_seq, bounded_limit),
            ).fetchall()
        return [
            {**{key: value for key, value in dict(row).items() if key != "payload_json"},
             "payload": json.loads(row["payload_json"])}
            for row in rows
        ]

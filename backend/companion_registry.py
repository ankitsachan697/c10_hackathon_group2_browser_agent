"""One-time pairing and revocable companion device credentials."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

try:
    from .database import Database
except ImportError:
    from database import Database


class CompanionError(RuntimeError):
    pass


class CompanionRegistry:
    def __init__(self, database: Database, admin_token: str | None):
        self.database = database
        self.admin_token = admin_token

    def _hash(self, value: str) -> str:
        if not self.admin_token:
            raise CompanionError("Companion pairing is not configured")
        return hmac.new(self.admin_token.encode(), value.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def issue_pair_code(self, user_scope: str) -> dict[str, str]:
        if not user_scope or len(user_scope) > 100:
            raise CompanionError("Invalid companion scope")
        code = secrets.token_urlsafe(12)
        expires = self._now() + timedelta(minutes=5)
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO companion_pair_codes(code_hash,user_scope,expires_at,created_at) VALUES (?,?,?,?)",
                (self._hash(code), user_scope, expires.isoformat(), self._now().isoformat()),
            )
        return {"code": code, "expires_at": expires.isoformat()}

    def exchange(self, code: str, device_name: str) -> dict[str, str]:
        if not code or not device_name.strip() or len(device_name) > 100:
            raise CompanionError("Invalid pair code or device name")
        credential = secrets.token_urlsafe(32)
        device_id = f"dev_{uuid.uuid4().hex}"
        code_hash = self._hash(code)
        now = self._now().isoformat()
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM companion_pair_codes WHERE code_hash=?", (code_hash,)).fetchone()
            if not row or row["used_at"] or row["expires_at"] <= now:
                raise CompanionError("Pair code is invalid, expired, or already used")
            connection.execute("UPDATE companion_pair_codes SET used_at=? WHERE code_hash=?", (now, code_hash))
            connection.execute(
                "INSERT INTO companions(id,name,user_scope,credential_hash,created_at) VALUES (?,?,?,?,?)",
                (device_id, device_name.strip(), row["user_scope"], self._hash(credential), now),
            )
        return {"id": device_id, "name": device_name.strip(), "credential": credential}

    def authenticate(self, device_id: str, credential: str) -> dict:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM companions WHERE id=?", (device_id,)).fetchone()
        if not row or row["revoked_at"] or not credential or not hmac.compare_digest(row["credential_hash"], self._hash(credential)):
            raise CompanionError("Companion credential is invalid or revoked")
        return dict(row)

    def heartbeat(self, device_id: str, credential: str) -> None:
        self.authenticate(device_id, credential)
        with self.database.transaction() as connection:
            connection.execute("UPDATE companions SET last_seen=? WHERE id=?", (self._now().isoformat(), device_id))

    def list_online(self) -> list[dict[str, object]]:
        cutoff = (self._now() - timedelta(seconds=30)).isoformat()
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id,name FROM companions WHERE revoked_at IS NULL AND last_seen>=? ORDER BY name",
                (cutoff,),
            ).fetchall()
        return [{"id": row["id"], "name": row["name"], "online": True} for row in rows]

    def revoke(self, device_id: str) -> None:
        with self.database.transaction() as connection:
            connection.execute("UPDATE companions SET revoked_at=? WHERE id=?", (self._now().isoformat(), device_id))

"""Authenticated encryption boundary for reusable journey credentials."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class CredentialVaultError(ValueError):
    pass


class CredentialVault:
    def __init__(self, key: str | None):
        if not key:
            raise CredentialVaultError("CREDENTIAL_ENCRYPTION_KEY is required")
        try:
            self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as error:
            raise CredentialVaultError("CREDENTIAL_ENCRYPTION_KEY is invalid") from error

    @classmethod
    def for_database(cls, database_path: str | Path, configured_key: str | None = None) -> "CredentialVault":
        """Open a stable local key, or use an explicitly supplied deployment key."""
        database_path = Path(database_path)
        key_path = database_path.with_suffix(".credentials.key")
        if configured_key:
            vault = cls(configured_key)
            if key_path.exists() or key_path.is_symlink():
                if key_path.is_symlink() or not stat.S_ISREG(key_path.stat().st_mode):
                    raise CredentialVaultError("Credential key path is not a regular file")
                if key_path.read_text(encoding="ascii").strip() != configured_key:
                    raise CredentialVaultError("Configured credential key differs from the stored key")
            else:
                key_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    return cls.for_database(database_path, configured_key)
                else:
                    with os.fdopen(descriptor, "w", encoding="ascii") as output:
                        output.write(configured_key)
                        output.flush()
                        os.fsync(output.fileno())
            return vault

        if key_path.exists() or key_path.is_symlink():
            if key_path.is_symlink() or not stat.S_ISREG(key_path.stat().st_mode):
                raise CredentialVaultError("Credential key path is not a regular file")
            return cls(key_path.read_text(encoding="ascii").strip())

        if database_path.exists():
            try:
                with sqlite3.connect(database_path) as connection:
                    existing = connection.execute(
                        "SELECT 1 FROM journeys WHERE credential_ciphertext IS NOT NULL LIMIT 1"
                    ).fetchone()
            except sqlite3.OperationalError:
                existing = None
            if existing:
                raise CredentialVaultError("Credential key is missing for existing credentials")

        key_path.parent.mkdir(parents=True, exist_ok=True)
        generated = Fernet.generate_key()
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return cls.for_database(database_path)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(generated)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            key_path.unlink(missing_ok=True)
            raise
        return cls(generated.decode("ascii"))

    def encrypt(self, username: str, password: str) -> str:
        payload = json.dumps({"username": username, "password": password}, separators=(",", ":")).encode()
        return self._fernet.encrypt(payload).decode()

    def decrypt(self, ciphertext: str) -> tuple[str, str]:
        try:
            payload = json.loads(self._fernet.decrypt(ciphertext.encode()).decode())
            return str(payload["username"]), str(payload["password"])
        except (InvalidToken, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise CredentialVaultError("Unable to decrypt journey credentials") from error

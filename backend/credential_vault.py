"""Authenticated encryption boundary for reusable journey credentials."""

from __future__ import annotations

import json

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

    def encrypt(self, username: str, password: str) -> str:
        payload = json.dumps({"username": username, "password": password}, separators=(",", ":")).encode()
        return self._fernet.encrypt(payload).decode()

    def decrypt(self, ciphertext: str) -> tuple[str, str]:
        try:
            payload = json.loads(self._fernet.decrypt(ciphertext.encode()).decode())
            return str(payload["username"]), str(payload["password"])
        except (InvalidToken, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise CredentialVaultError("Unable to decrypt journey credentials") from error

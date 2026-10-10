"""Redact known credentials and recognizable payment details from text evidence."""

from __future__ import annotations

import re
from typing import Iterable


CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
LABELLED_VALUE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api_key|auth_token|auth_secret|user_password|cvv|cvc|security_code)"
    r"\s*[:=]\s*(['\"]?)([^\s'\"<>]+)\2"
)


def _luhn_valid(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


class SensitiveDataRedactor:
    def __init__(self, secrets: Iterable[str] = ()):
        self.secrets = {str(secret).strip() for secret in secrets if secret and len(str(secret).strip()) > 2}

    def add_secret(self, secret: str) -> None:
        if secret and len(secret.strip()) > 2:
            self.secrets.add(secret.strip())

    def redact(self, text: str) -> str:
        if not text:
            return text
        sanitized = text
        for secret in sorted(self.secrets, key=len, reverse=True):
            sanitized = sanitized.replace(secret, "[REDACTED]")
        sanitized = LABELLED_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", sanitized)
        sanitized = CARD_CANDIDATE.sub(
            lambda match: "[REDACTED_CARD]" if _luhn_valid(match.group(0)) else match.group(0),
            sanitized,
        )
        return sanitized

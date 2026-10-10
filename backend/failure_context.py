"""Deterministic failure classification and token-bounded repair context."""

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class FailureLimits:
    traceback_chars: int = 4000
    dom_chars: int = 6000
    script_chars: int = 12000
    action_chars: int = 500
    locator_items: int = 10
    locator_chars: int = 300
    artifact_items: int = 10
    artifact_chars: int = 300


@dataclass(frozen=True)
class FailureDecision:
    category: str
    eligible: bool
    reason: str


@dataclass(frozen=True)
class FailurePacket:
    category: str
    original_script: str
    failed_action: str
    traceback: str
    dom_excerpt: str
    locator_evidence: tuple[str, ...]
    artifact_references: tuple[str, ...]


def classify_failure(result: dict[str, Any]) -> FailureDecision:
    message = f"{result.get('stderr', '')}\n{result.get('stdout', '')}".lower()
    if any(token in message for token in ("unauthorized", "invalid credential", "401", "403", "csrf")):
        return FailureDecision("AUTHENTICATION", False, "Authentication requires attention")
    if any(token in message for token in ("browser executable", "connection refused", "no space left", "network is unreachable")):
        return FailureDecision("INFRASTRUCTURE", False, "Execution infrastructure is unavailable")
    if any(token in message for token in ("assertionerror", "expect(", "assert ")):
        return FailureDecision("ASSERTION", False, "Product expectations are not auto-rewritten")
    if any(token in message for token in ("timeout", "timed out")):
        return FailureDecision("TIMEOUT", True, "Timing or locator wait may be repairable")
    if any(token in message for token in ("locator", "element not found", "strict mode violation", "selector")):
        return FailureDecision("BROKEN_SELECTOR", True, "Locator appears stale or ambiguous")
    return FailureDecision("UNKNOWN", False, "Failure is not safely repairable")


def _redact(value: str, secrets: Iterable[str]) -> str:
    clean = value or ""
    for secret in secrets:
        if secret:
            clean = clean.replace(secret, "[REDACTED]")
    return re.sub(r"(?i)(password|token|secret)\s*[:=]\s*['\"]?[^\s'\"]+", r"\1=[REDACTED]", clean)


def build_failure_packet(result: dict[str, Any], limits: FailureLimits | None = None, secrets: Iterable[str] = ()) -> FailurePacket:
    limits = limits or FailureLimits()
    decision = classify_failure(result)
    traceback = _redact(result.get("stderr") or result.get("stdout") or "", secrets)[-limits.traceback_chars:]
    dom_excerpt = _redact(result.get("dom_excerpt") or result.get("dom_snapshot") or "", secrets)[:limits.dom_chars]
    return FailurePacket(
        category=decision.category,
        original_script=_redact(str(result.get("script_snapshot") or ""), secrets)[:limits.script_chars],
        failed_action=_redact(str(result.get("failed_action") or ""), secrets)[:limits.action_chars],
        traceback=traceback,
        dom_excerpt=dom_excerpt,
        locator_evidence=tuple(_redact(str(item), secrets)[:limits.locator_chars] for item in result.get("locator_evidence", [])[:limits.locator_items]),
        artifact_references=tuple(str(item)[:limits.artifact_chars] for item in result.get("screenshots", [])[:limits.artifact_items] if item),
    )

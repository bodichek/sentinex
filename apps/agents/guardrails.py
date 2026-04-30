"""Mandatory guardrails: every agent invocation passes through these."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.core.models import ComplianceLog, LLMUsage, Tenant, TenantBudget, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MaskedText:
    text: str
    mask_map: dict[str, str]


# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[ \-.]?)?(?:\(?\d{2,4}\)?[ \-.]?)?\d{3}[ \-.]?\d{3}[ \-.]?\d{3,4}")
_CZ_BIRTHNUM_RE = re.compile(r"\b\d{6}/?\d{3,4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def mask_pii(text: str, existing_map: dict[str, str] | None = None) -> MaskedText:
    mask_map: dict[str, str] = dict(existing_map or {})
    counters: dict[str, int] = {}

    def _replace(kind: str, pattern: re.Pattern[str], raw: str) -> str:
        def sub(match: re.Match[str]) -> str:
            value = match.group(0)
            for token, original in mask_map.items():
                if original == value:
                    return token
            idx = counters.get(kind, 0)
            counters[kind] = idx + 1
            token = f"[{kind}_{idx}]"
            mask_map[token] = value
            return token
        return pattern.sub(sub, raw)

    out = text
    out = _replace("EMAIL", _EMAIL_RE, out)
    out = _replace("CARD", _CARD_RE, out)
    out = _replace("RC", _CZ_BIRTHNUM_RE, out)
    out = _replace("PHONE", _PHONE_RE, out)
    return MaskedText(text=out, mask_map=mask_map)


def unmask_pii(text: str, mask_map: dict[str, str]) -> str:
    out = text
    for token, original in mask_map.items():
        out = out.replace(token, original)
    return out


# ---------------------------------------------------------------------------
# Cost budget
# ---------------------------------------------------------------------------


def check_cost_budget(tenant: Tenant | None, estimated_cost_czk: Decimal) -> CheckResult:
    if tenant is None:
        return CheckResult(ok=True, reason="no-tenant")
    budget, _ = TenantBudget.objects.get_or_create(tenant=tenant)

    # Current month spent from LLMUsage (authoritative).
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = (
        LLMUsage.objects.filter(tenant=tenant, created_at__gte=month_start)
        .values_list("cost_czk", flat=True)
    )
    total = sum((Decimal(x) for x in spent), start=Decimal("0"))

    if total + estimated_cost_czk > budget.monthly_limit_czk:
        return CheckResult(
            ok=False,
            reason="monthly budget exceeded",
            data={"spent": str(total), "limit": str(budget.monthly_limit_czk)},
        )
    return CheckResult(ok=True, data={"spent": str(total), "limit": str(budget.monthly_limit_czk)})


# ---------------------------------------------------------------------------
# Scope check
# ---------------------------------------------------------------------------


ALLOWED_AGENT_ACTIONS = {
    "orchestrator": {"classify", "compose"},
    "strategic": {"analyze"},
    "finance": {"analyze"},
    "people": {"analyze"},
    "ops": {"analyze"},
    "knowledge": {"analyze"},
}


def check_scope(agent: str, action: str) -> CheckResult:
    allowed = ALLOWED_AGENT_ACTIONS.get(agent, set())
    if action not in allowed:
        return CheckResult(ok=False, reason=f"action '{action}' not permitted for agent '{agent}'")
    return CheckResult(ok=True)


# ---------------------------------------------------------------------------
# Prompt injection detection
# ---------------------------------------------------------------------------


_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "you are now",
    "system prompt:",
    "</system>",
    "<|im_start|>",
    "zapomeň na předchozí instrukce",
)


def detect_prompt_injection(text: str) -> CheckResult:
    haystack = text.lower()
    for marker in _INJECTION_MARKERS:
        if marker in haystack:
            return CheckResult(ok=False, reason=f"possible prompt injection: '{marker}'")
    return CheckResult(ok=True)


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------


def validate_output_format(text: str, *, min_length: int = 1, max_length: int = 100_000) -> CheckResult:
    if not text or len(text) < min_length:
        return CheckResult(ok=False, reason="output too short")
    if len(text) > max_length:
        return CheckResult(ok=False, reason="output exceeds max length")
    return CheckResult(ok=True)


# ---------------------------------------------------------------------------
# Compliance log
# ---------------------------------------------------------------------------


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def log_for_compliance(
    *,
    tenant: Tenant | None,
    user: User | None,
    agent: str,
    model: str,
    prompt: str,
    response: str = "",
    success: bool = True,
    error: str = "",
) -> ComplianceLog:
    return ComplianceLog.objects.create(
        tenant=tenant,
        user=user,
        agent=agent,
        model=model,
        prompt_hash=_hash(prompt),
        response_hash=_hash(response) if response else "",
        success=success,
        error=error[:200],
    )

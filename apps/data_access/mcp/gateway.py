"""MCP Gateway — single chokepoint for MCP server calls.

Handles credential decryption, token refresh, audit logging, and rate limiting.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from django.core.cache import cache
from django.utils import timezone

from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Credential, Integration, MCPCall

logger = logging.getLogger(__name__)

RATE_LIMIT_PER_MINUTE = 60


class RateLimitExceeded(Exception):
    """Raised when tenant-level rate limit is exceeded."""


class MCPGateway:
    def __init__(self, integrations: dict[str, MCPIntegration]) -> None:
        self._integrations = integrations

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any] | None = None
    ) -> MCPCallResult:
        params = params or {}
        impl = self._integrations.get(integration.provider)
        if impl is None:
            raise ValueError(f"No MCP implementation registered for '{integration.provider}'")

        self._enforce_rate_limit(integration)

        credential = Credential.objects.filter(integration=integration).first()
        if credential is None:
            return MCPCallResult(ok=False, error="no credential")
        tokens = credential.get_tokens()

        # Refresh if expiring soon.
        expires_at = tokens.get("expires_at")
        if expires_at and self._expiring_soon(expires_at):
            tokens = impl.refresh_tokens(tokens)
            credential.set_tokens(tokens)
            credential.save(update_fields=["encrypted_tokens", "updated_at"])

        start = time.monotonic()
        try:
            result = impl.call(integration, tool, params)
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._audit(integration, tool, params, ok=False, error=str(exc), latency_ms=latency_ms)
            logger.exception("MCP call failed: %s.%s", integration.provider, tool)
            return MCPCallResult(ok=False, error=str(exc))

        latency_ms = int((time.monotonic() - start) * 1000)
        self._audit(
            integration, tool, params, ok=result.ok, error=result.error, latency_ms=latency_ms
        )
        return result

    # ------------------------------------------------------------------

    def _enforce_rate_limit(self, integration: Integration) -> None:
        key = f"mcp:rl:{integration.pk}:{int(time.time() // 60)}"
        n = cache.get(key) or 0
        if n >= RATE_LIMIT_PER_MINUTE:
            raise RateLimitExceeded(f"rate limit for integration {integration.pk}")
        cache.set(key, n + 1, 120)

    def _audit(
        self,
        integration: Integration,
        tool: str,
        params: dict[str, Any],
        *,
        ok: bool,
        error: str,
        latency_ms: int,
    ) -> None:
        payload = json.dumps(params, sort_keys=True, default=str).encode("utf-8")
        MCPCall.objects.create(
            integration=integration,
            tool=tool,
            params_hash=hashlib.sha256(payload).hexdigest(),
            ok=ok,
            error=error[:200],
            latency_ms=latency_ms,
        )

    def _expiring_soon(self, iso: str) -> bool:
        from datetime import datetime

        try:
            expires = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            return False
        return (expires - timezone.now()).total_seconds() < 300

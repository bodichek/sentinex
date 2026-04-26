"""Google Workspace MCP integration.

Builds auth URLs and exchanges OAuth codes against Google. For the actual
MCP tool invocation we defer to the Anthropic Google Workspace MCP server;
calls are proxied via HTTP when ``SENTINEX_MCP_GW_URL`` is configured,
otherwise a stub response is returned and logged (useful for dev without
the MCP server running).
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.utils import timezone

from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleWorkspaceIntegration(MCPIntegration):
    provider = "google_workspace"

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(settings.GOOGLE_OAUTH_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        data = {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        response = httpx.post(GOOGLE_TOKEN_URL, data=data, timeout=15.0)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return self._enrich(payload)

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        data = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": tokens.get("refresh_token", ""),
            "grant_type": "refresh_token",
        }
        response = httpx.post(GOOGLE_TOKEN_URL, data=data, timeout=15.0)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        payload.setdefault("refresh_token", tokens.get("refresh_token"))
        return self._enrich(payload)

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        mcp_url = os.environ.get("SENTINEX_MCP_GW_URL")
        if not mcp_url:
            logger.info("MCP gateway URL not set — returning stub for %s", tool)
            return MCPCallResult(ok=True, data={"stub": True, "tool": tool, "params": params})
        try:
            response = httpx.post(
                f"{mcp_url.rstrip('/')}/call",
                json={"provider": self.provider, "tool": tool, "params": params},
                timeout=60.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return MCPCallResult(ok=False, error=str(exc))
        return MCPCallResult(ok=True, data=response.json())

    def _enrich(self, payload: dict[str, Any]) -> dict[str, Any]:
        expires_in = int(payload.get("expires_in", 3600))
        payload["expires_at"] = (timezone.now() + timedelta(seconds=expires_in)).isoformat()
        return payload

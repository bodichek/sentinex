from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.microsoft365 import oauth
from apps.connectors.microsoft365.client import Microsoft365Client
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "microsoft365"


class Microsoft365Integration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return oauth.authorization_url(state, redirect_uri)

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        return oauth.exchange_code(code, redirect_uri)

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return oauth.refresh_tokens(tokens)

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with Microsoft365Client(integration) as client:
                if tool == "me":
                    return MCPCallResult(ok=True, data=client.me())
                if tool == "mail.list":
                    return MCPCallResult(ok=True, data=client.list_messages(**params))
                if tool == "calendar.list":
                    return MCPCallResult(ok=True, data=client.list_calendar_events(**params))
                if tool == "onedrive.root":
                    return MCPCallResult(ok=True, data=client.list_drive_root(**params))
                if tool == "teams.list":
                    return MCPCallResult(ok=True, data=client.list_joined_teams())
                if tool == "teams.channels.list":
                    return MCPCallResult(ok=True, data=client.list_channels(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("MS365 HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("MS365 failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

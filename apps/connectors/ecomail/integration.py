from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.ecomail.client import EcomailClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "ecomail"


class EcomailIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return "/integrations/ecomail/setup/"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        if not code:
            raise ValueError("expected api_key")
        return {"api_key": code}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with EcomailClient(integration) as client:
                if tool == "ping":
                    return MCPCallResult(ok=True, data=client.ping())
                if tool == "lists.list":
                    return MCPCallResult(ok=True, data=client.list_lists())
                if tool == "campaigns.list":
                    return MCPCallResult(ok=True, data=client.list_campaigns())
                if tool == "campaign.stats":
                    return MCPCallResult(ok=True, data=client.campaign_stats(**params))
                if tool == "subscribers.list":
                    return MCPCallResult(ok=True, data=client.list_subscribers(**params))
                if tool == "automations.list":
                    return MCPCallResult(ok=True, data=client.list_automations())
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Ecomail HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Ecomail failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

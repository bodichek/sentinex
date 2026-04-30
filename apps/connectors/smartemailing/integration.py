"""SmartEmailing MCP integration — Basic Auth (no OAuth)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.smartemailing.client import SmartEmailingClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "smartemailing"


class SmartEmailingIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        # SmartEmailing has no OAuth — credentials are pasted in the setup wizard.
        return "/integrations/smartemailing/setup/"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        # `code` here carries `username:api_key` from the setup form.
        username, _, api_key = code.partition(":")
        if not username or not api_key:
            raise ValueError("expected 'username:api_key'")
        return {"username": username, "api_key": api_key}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with SmartEmailingClient(integration) as client:
                if tool == "ping":
                    return MCPCallResult(ok=True, data=client.ping())
                if tool == "contactlists.list":
                    return MCPCallResult(ok=True, data=client.list_contactlists())
                if tool == "contacts.count":
                    return MCPCallResult(ok=True, data={"count": client.count_contacts(**params)})
                if tool == "campaigns.list":
                    return MCPCallResult(ok=True, data=client.iter_campaigns(**params))
                if tool == "campaign.stats":
                    return MCPCallResult(ok=True, data=client.campaign_stats(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("SmartEmailing HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("SmartEmailing failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

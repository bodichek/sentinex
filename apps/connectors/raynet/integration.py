"""Raynet CRM MCP-style integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.raynet.client import RaynetClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "raynet"


class RaynetIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return "/integrations/raynet/setup/"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        # ``code`` carries ``instance:username:api_key`` from the setup form.
        parts = code.split(":", 2)
        if len(parts) != 3 or not all(parts):
            raise ValueError("expected 'instance:username:api_key'")
        return {"instance": parts[0], "username": parts[1], "api_key": parts[2]}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with RaynetClient(integration) as client:
                if tool == "ping":
                    return MCPCallResult(ok=True, data=client.ping())
                if tool == "companies.list":
                    return MCPCallResult(ok=True, data=client.list_companies(**params))
                if tool == "leads.list":
                    return MCPCallResult(ok=True, data=client.list_leads(**params))
                if tool == "business_cases.list":
                    return MCPCallResult(ok=True, data=client.list_business_cases(**params))
                if tool == "offers.list":
                    return MCPCallResult(ok=True, data=client.list_offers(**params))
                if tool == "invoices.list":
                    return MCPCallResult(ok=True, data=client.list_invoices(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Raynet HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Raynet failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

"""Caflou MCP-style integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.caflou.client import CaflouClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "caflou"


class CaflouIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return "/integrations/caflou/setup/"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        if not code:
            raise ValueError("expected api_token")
        return {"api_token": code}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with CaflouClient(integration) as client:
                if tool == "ping":
                    return MCPCallResult(ok=True, data=client.ping())
                if tool == "companies.list":
                    return MCPCallResult(ok=True, data=client.list_companies(**params))
                if tool == "projects.list":
                    return MCPCallResult(ok=True, data=client.list_projects(**params))
                if tool == "tasks.list":
                    return MCPCallResult(ok=True, data=client.list_tasks(**params))
                if tool == "invoices.list":
                    return MCPCallResult(ok=True, data=client.list_invoices(**params))
                if tool == "timesheets.list":
                    return MCPCallResult(ok=True, data=client.list_timesheets(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Caflou HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Caflou failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

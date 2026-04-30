from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.fapi.client import FapiClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "fapi"


class FapiIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return "/integrations/fapi/setup/"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        # ``code`` carries ``user@email.cz:api_key``.
        user, _, api_key = code.partition(":")
        if not user or not api_key:
            raise ValueError("expected 'user:api_key'")
        return {"user": user, "api_key": api_key}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with FapiClient(integration) as client:
                if tool == "ping":
                    return MCPCallResult(ok=True, data=client.ping())
                if tool == "invoices.list":
                    return MCPCallResult(ok=True, data=client.list_invoices(**params))
                if tool == "items.list":
                    return MCPCallResult(ok=True, data=client.list_items(**params))
                if tool == "clients.list":
                    return MCPCallResult(ok=True, data=client.list_clients(**params))
                if tool == "vouchers.list":
                    return MCPCallResult(ok=True, data=client.list_vouchers(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("FAPI HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("FAPI failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

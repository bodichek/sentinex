from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.salesforce import oauth
from apps.connectors.salesforce.client import SalesforceClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "salesforce"


class SalesforceIntegration(MCPIntegration):
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
            with SalesforceClient(integration) as client:
                if tool == "query":
                    return MCPCallResult(ok=True, data=client.query(**params))
                if tool == "accounts.list":
                    return MCPCallResult(ok=True, data=client.list_accounts(**params))
                if tool == "opportunities.list":
                    return MCPCallResult(ok=True, data=client.list_opportunities(**params))
                if tool == "leads.list":
                    return MCPCallResult(ok=True, data=client.list_leads(**params))
                if tool == "users.list":
                    return MCPCallResult(ok=True, data=client.list_users(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Salesforce HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Salesforce failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

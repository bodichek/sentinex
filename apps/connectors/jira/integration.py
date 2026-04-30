from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.jira import oauth
from apps.connectors.jira.client import JiraClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "jira"


class JiraIntegration(MCPIntegration):
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
            with JiraClient(integration) as client:
                if tool == "myself":
                    return MCPCallResult(ok=True, data=client.myself())
                if tool == "projects.list":
                    return MCPCallResult(ok=True, data=client.list_projects())
                if tool == "search":
                    return MCPCallResult(ok=True, data=client.search(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Jira HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Jira failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

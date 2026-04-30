from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.mailchimp import oauth
from apps.connectors.mailchimp.client import MailchimpClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "mailchimp"


class MailchimpIntegration(MCPIntegration):
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
            with MailchimpClient(integration) as client:
                if tool == "ping":
                    return MCPCallResult(ok=True, data=client.ping())
                if tool == "audiences.list":
                    return MCPCallResult(ok=True, data=client.list_audiences(**params))
                if tool == "campaigns.list":
                    return MCPCallResult(ok=True, data=client.list_campaigns(**params))
                if tool == "campaign.report":
                    return MCPCallResult(ok=True, data=client.campaign_report(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Mailchimp HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Mailchimp failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

from __future__ import annotations

import logging
from typing import Any

from apps.connectors.notion import client as notion_client
from apps.connectors.notion import oauth
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
PROVIDER = "notion"


def _credential(integration: Integration) -> Credential:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Notion integration has no credential")
    return cred


class NotionIntegration(MCPIntegration):
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
            credential = _credential(integration)
            access_token = (credential.get_tokens() or {}).get("access_token")
            if not access_token:
                return MCPCallResult(ok=False, error="missing access_token")
            result = notion_client.call_tool(access_token, tool, params)
            if result.is_error:
                return MCPCallResult(
                    ok=False,
                    error="; ".join(result.text_blocks) or "tool returned isError",
                )
            payload = result.first_json()
            return MCPCallResult(
                ok=True,
                data=payload if payload is not None else {"text": result.text_blocks},
            )
        except Exception as exc:
            logger.exception("Notion tool %s failed", tool)
            return MCPCallResult(ok=False, error=str(exc))

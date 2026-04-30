"""Trello MCP-style integration — API key + token (paste flow)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.trello.client import TrelloClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "trello"


class TrelloIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return "/integrations/trello/setup/"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        api_key, _, token = code.partition(":")
        if not api_key or not token:
            raise ValueError("expected 'api_key:token'")
        return {"api_key": api_key, "token": token}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with TrelloClient(integration) as client:
                if tool == "me":
                    return MCPCallResult(ok=True, data=client.me())
                if tool == "boards.list":
                    return MCPCallResult(ok=True, data=client.list_boards())
                if tool == "lists.list":
                    return MCPCallResult(ok=True, data=client.list_lists(**params))
                if tool == "cards.list":
                    return MCPCallResult(ok=True, data=client.list_cards(**params))
                if tool == "actions.list":
                    return MCPCallResult(ok=True, data=client.list_actions(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Trello HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Trello failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

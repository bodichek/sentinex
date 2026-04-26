"""Slack MCP integration — Bot Token auth, encrypted via Credential model."""

from __future__ import annotations

import logging
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)


def _bot_token(integration: Integration) -> str:
    credential = Credential.objects.filter(integration=integration).first()
    if credential is None:
        raise ValueError("Slack integration has no credential")
    tokens = credential.get_tokens()
    token = tokens.get("bot_token") or tokens.get("access_token")
    if not token:
        raise ValueError("Slack credential is missing 'bot_token'")
    return str(token)


class SlackClient:
    """Thin wrapper over slack-sdk's ``WebClient`` resolving the bot token from the encrypted credential."""

    def __init__(self, integration: Integration, *, web_client: WebClient | None = None) -> None:
        self._integration = integration
        self._client = web_client if web_client is not None else WebClient(token=_bot_token(integration))

    @property
    def web(self) -> WebClient:
        return self._client

    def list_joined_channels(self, limit: int = 200) -> list[dict[str, Any]]:
        result = self._client.conversations_list(types="public_channel,private_channel", limit=limit)
        channels = result.get("channels") or []
        return [c for c in channels if c.get("is_member")]

    def fetch_messages(self, channel_id: str, oldest_ts: float, limit: int = 200) -> list[dict[str, Any]]:
        result = self._client.conversations_history(
            channel=channel_id, oldest=str(oldest_ts), limit=limit
        )
        return list(result.get("messages") or [])

    def list_users(self, limit: int = 200) -> list[dict[str, Any]]:
        result = self._client.users_list(limit=limit)
        return list(result.get("members") or [])


class SlackIntegration(MCPIntegration):
    """MCP-style integration. Slack uses bot tokens — no OAuth refresh in this MVP."""

    provider = "slack"

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        # Slack bot-token model: token is provisioned out-of-band and stored
        # via the admin / setup flow. Returning the install hint is enough.
        return "https://api.slack.com/apps"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        # Bot tokens are pasted, not OAuth-exchanged here.
        return {"bot_token": code}

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        # Bot tokens don't expire under the simple install flow.
        return tokens

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            client = SlackClient(integration)
            if tool == "channels.list":
                return MCPCallResult(ok=True, data=client.list_joined_channels(**params))
            if tool == "users.list":
                return MCPCallResult(ok=True, data=client.list_users(**params))
            if tool == "channels.history":
                return MCPCallResult(ok=True, data=client.fetch_messages(**params))
            return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except SlackApiError as exc:
            logger.warning("Slack API error in %s: %s", tool, exc)
            return MCPCallResult(ok=False, error=str(exc))
        except Exception as exc:
            logger.exception("Slack integration failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

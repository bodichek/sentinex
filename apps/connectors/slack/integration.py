"""Slack MCP integration with OAuth v2 install flow."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import httpx
from django.conf import settings
from slack_sdk.errors import SlackApiError

from apps.connectors.slack.client import SlackClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "slack"
AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
TOKEN_URL = "https://slack.com/api/oauth.v2.access"

DEFAULT_BOT_SCOPES = (
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "users:read",
    "users:read.email",
    "team:read",
    "usergroups:read",
    "reactions:read",
)


class SlackIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        client_id = getattr(settings, "SLACK_CLIENT_ID", "")
        if not client_id:
            # Fallback: legacy bot-token paste flow.
            return "https://api.slack.com/apps"
        params = {
            "client_id": client_id,
            "scope": ",".join(DEFAULT_BOT_SCOPES),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        client_id = getattr(settings, "SLACK_CLIENT_ID", "")
        client_secret = getattr(settings, "SLACK_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            # Legacy bot-token paste flow.
            return {"bot_token": code}
        resp = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Slack OAuth error: {payload.get('error', 'unknown')}")
        return {
            "bot_token": payload.get("access_token"),
            "bot_user_id": payload.get("bot_user_id"),
            "team_id": (payload.get("team") or {}).get("id"),
            "team_name": (payload.get("team") or {}).get("name"),
            "scope": payload.get("scope"),
        }

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        # Slack v2 bot tokens do not expire under the default install flow.
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
            if tool == "team.info":
                return MCPCallResult(ok=True, data=client.team_info())
            if tool == "usergroups.list":
                return MCPCallResult(ok=True, data=client.usergroups_list())
            return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except SlackApiError as exc:
            logger.warning("Slack API error in %s: %s", tool, exc)
            return MCPCallResult(ok=False, error=str(exc))
        except Exception as exc:
            logger.exception("Slack integration failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

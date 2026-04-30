"""Slack Web API client backed by the encrypted Credential row."""

from __future__ import annotations

import logging
from typing import Any

from slack_sdk import WebClient

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)


def bot_token(integration: Integration) -> str:
    credential = Credential.objects.filter(integration=integration).first()
    if credential is None:
        raise ValueError("Slack integration has no credential")
    tokens = credential.get_tokens()
    token = tokens.get("bot_token") or tokens.get("access_token")
    if not token:
        raise ValueError("Slack credential is missing 'bot_token'")
    return str(token)


class SlackClient:
    """Read-only wrapper over slack_sdk.WebClient."""

    def __init__(
        self, integration: Integration, *, web_client: WebClient | None = None
    ) -> None:
        self._integration = integration
        self._client = web_client or WebClient(token=bot_token(integration))

    @property
    def web(self) -> WebClient:
        return self._client

    def list_joined_channels(self, limit: int = 200) -> list[dict[str, Any]]:
        result = self._client.conversations_list(
            types="public_channel,private_channel", limit=limit
        )
        channels = result.get("channels") or []
        return [c for c in channels if c.get("is_member")]

    def fetch_messages(
        self, channel_id: str, oldest_ts: float, limit: int = 200
    ) -> list[dict[str, Any]]:
        result = self._client.conversations_history(
            channel=channel_id, oldest=str(oldest_ts), limit=limit
        )
        return list(result.get("messages") or [])

    def list_users(self, limit: int = 200) -> list[dict[str, Any]]:
        result = self._client.users_list(limit=limit)
        return list(result.get("members") or [])

    def team_info(self) -> dict[str, Any]:
        return dict(self._client.team_info().get("team") or {})

    def usergroups_list(self) -> list[dict[str, Any]]:
        return list(self._client.usergroups_list().get("usergroups") or [])

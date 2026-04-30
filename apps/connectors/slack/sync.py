"""Slack sync pipeline — emits aggregated metrics to DataSnapshot."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.slack.client import SlackClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


class SlackSyncPipeline:
    source = "slack"

    def __init__(self, *, client: SlackClient | None = None) -> None:
        self._client = client

    def _resolve_client(self, integration: Integration) -> SlackClient:
        return self._client or SlackClient(integration)

    def sync_channels(self, integration: Integration) -> list[dict[str, Any]]:
        client = self._resolve_client(integration)
        return [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "num_members": c.get("num_members", 0),
                "is_private": c.get("is_private", False),
            }
            for c in client.list_joined_channels()
        ]

    def sync_messages(
        self, integration: Integration, channels: list[dict[str, Any]], days: int = 7
    ) -> dict[str, Any]:
        client = self._resolve_client(integration)
        oldest_ts = (timezone.now() - timedelta(days=days)).timestamp()
        per_channel: dict[str, dict[str, Any]] = {}
        active_users: set[str] = set()
        total = 0
        for channel in channels:
            channel_id = channel.get("id")
            if not channel_id:
                continue
            messages = client.fetch_messages(channel_id, oldest_ts=oldest_ts)
            users = {m.get("user") for m in messages if m.get("user")}
            per_channel[channel.get("name") or channel_id] = {
                "count": len(messages),
                "unique_users": len(users),
                "thread_count": sum(1 for m in messages if m.get("thread_ts")),
            }
            active_users.update(u for u in users if isinstance(u, str))
            total += len(messages)
        return {
            "total_messages": total,
            "active_users": len(active_users),
            "per_channel": per_channel,
            "window_days": days,
        }

    def sync_users(self, integration: Integration) -> dict[str, int]:
        client = self._resolve_client(integration)
        users = client.list_users()
        humans = [u for u in users if not u.get("is_bot") and not u.get("deleted")]
        return {"total": len(users), "humans": len(humans), "bots": len(users) - len(humans)}


def run_sync(days: int = 7, pipeline: SlackSyncPipeline | None = None) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="slack", is_active=True).first()
    if integration is None:
        return None

    pipeline = pipeline or SlackSyncPipeline()
    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    channels = pipeline.sync_channels(integration)
    messages = pipeline.sync_messages(integration, channels, days=days)
    users = pipeline.sync_users(integration)

    snapshot = DataSnapshot.objects.create(
        source="slack",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "channels": {"data": {"items": channels, "count": len(channels)}, "ok": True},
            "messages": {"data": messages, "ok": True},
            "users": {"data": users, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

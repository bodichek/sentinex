"""Slack ingest — users → channels → messages, all keyed by identity.Person.

Three syncs:
    SlackUserSync      — pulls users.list, resolves Person, attaches slack_id identity
    SlackChannelSync   — pulls conversations.list (joined channels), upserts mirror
    SlackMessageSync   — pulls conversations.history for is_tracked=True channels
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from django.utils import timezone

from apps.connectors._framework.base_sync import BaseSync, SyncContext
from apps.connectors._framework.identity_hook import resolve_person
from apps.connectors._framework.rate_limit import TokenBucket
from apps.connectors.slack.client import SlackClient
from apps.connectors.slack.models import (
    ScbSlackChannel,
    ScbSlackMessage,
    ScbSlackWorkspace,
)
from apps.identity.models import (
    IdentityType,
    PersonIdentity,
    SourceSystem,
)

logger = logging.getLogger(__name__)
PROVIDER = "slack"
RATE_LIMIT = TokenBucket("slack", capacity=50, refill_per_sec=0.8)  # Tier 3


def _ts_to_dt(ts: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (TypeError, ValueError):
        return None


def _ensure_workspace(integration) -> ScbSlackWorkspace:
    with SlackClient(integration) as client:
        team = client.team_info()
    ws, _ = ScbSlackWorkspace.objects.update_or_create(
        integration=integration,
        defaults={
            "team_id": team.get("id") or "unknown",
            "name": team.get("name") or "",
            "domain": team.get("domain") or "",
            "raw_payload": team,
            "last_synced_at": timezone.now(),
        },
    )
    return ws


class SlackUserSync(BaseSync):
    provider = PROVIDER
    resource = "users"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with SlackClient(self.integration) as client:
            yield from client.list_users()

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        if raw.get("is_bot") or raw.get("deleted"):
            return "skipped"
        slack_user_id = raw.get("id")
        profile = raw.get("profile") or {}
        email = profile.get("email") or ""
        real_name = profile.get("real_name") or raw.get("real_name") or raw.get("name") or ""
        person = resolve_person(
            source_system=PROVIDER,
            email=email or None,
            full_name=real_name or None,
            slack_id=slack_user_id,
        )
        if person is None:
            return "skipped"

        identity, created = PersonIdentity.objects.update_or_create(
            identity_type=IdentityType.SLACK_ID,
            identity_value=slack_user_id,
            defaults={
                "person": person,
                "source_system": SourceSystem.SLACK,
                "verified": bool(email),
                "last_seen": timezone.now(),
            },
        )
        return "created" if created else "updated"


class SlackChannelSync(BaseSync):
    provider = PROVIDER
    resource = "channels"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with SlackClient(self.integration) as client:
            yield from client.list_joined_channels()

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        workspace = _ensure_workspace(self.integration)
        slack_channel_id = raw.get("id")
        obj, created = ScbSlackChannel.objects.update_or_create(
            slack_channel_id=slack_channel_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": slack_channel_id,
                "source_synced_at": timezone.now(),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "workspace": workspace,
                "name": raw.get("name") or "",
                "purpose": (raw.get("purpose") or {}).get("value") or "",
                "topic": (raw.get("topic") or {}).get("value") or "",
                "is_private": bool(raw.get("is_private")),
                "is_archived": bool(raw.get("is_archived")),
                "member_count": int(raw.get("num_members") or 0),
            },
        )
        return "created" if created else "updated"


class SlackMessageSync(BaseSync):
    """Pulls messages from every channel with ``is_tracked=True``.

    Stores last synced ``ts`` per channel so the next run only fetches new
    messages.
    """

    provider = PROVIDER
    resource = "messages"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[tuple[str, dict[str, Any]]]:
        tracked = ScbSlackChannel.objects.filter(is_tracked=True, is_archived=False)
        with SlackClient(self.integration) as client:
            for channel in tracked:
                oldest = float(channel.last_message_synced_ts or 0)
                for msg in client.fetch_messages(channel.slack_channel_id, oldest_ts=oldest):
                    yield (channel.slack_channel_id, msg)

    def persist(self, raw_tuple: tuple[str, dict[str, Any]], ctx: SyncContext) -> str:
        channel_id, msg = raw_tuple
        channel = ScbSlackChannel.objects.get(slack_channel_id=channel_id)
        ts = msg.get("ts") or ""
        if not ts:
            return "skipped"
        slack_user_id = msg.get("user") or ""
        person = None
        if slack_user_id:
            ident = PersonIdentity.objects.filter(
                identity_type=IdentityType.SLACK_ID, identity_value=slack_user_id
            ).select_related("person").first()
            person = ident.person if ident else None

        obj, created = ScbSlackMessage.objects.update_or_create(
            channel=channel, ts=ts,
            defaults={
                "source_system": PROVIDER,
                "source_id": f"{channel_id}:{ts}",
                "source_synced_at": timezone.now(),
                "raw_payload": msg,
                "sync_run": ctx.run,
                "thread_ts": msg.get("thread_ts") or "",
                "slack_user_id": slack_user_id,
                "person": person,
                "text": msg.get("text") or "",
                "has_attachments": bool(msg.get("files") or msg.get("attachments")),
                "reactions": msg.get("reactions") or [],
                "posted_at": _ts_to_dt(ts),
            },
        )
        # advance channel cursor (use the highest ts we've seen)
        if ts > (channel.last_message_synced_ts or ""):
            channel.last_message_synced_ts = ts
            channel.save(update_fields=["last_message_synced_ts"])
        return "created" if created else "updated"

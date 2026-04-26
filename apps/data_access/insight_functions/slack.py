"""Slack Insight Function — feeds PeopleSpecialist + OpsSpecialist."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar, Literal

from django.utils import timezone

from apps.core.cache import cache_result
from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot

DataQuality = Literal["high", "partial", "low"]


@dataclass(frozen=True)
class SlackActivity:
    period_days: int
    total_messages: int
    active_users: int
    channel_count: int
    top_channels: list[dict[str, object]] = field(default_factory=list)
    bot_ratio: float = 0.0
    data_quality: DataQuality = "partial"

    TOP_N: ClassVar[int] = 5


@cache_result(ttl=3600, key_prefix="slack_activity")
def get_slack_activity(period_days: int = 7) -> SlackActivity:
    cutoff = timezone.now().date() - timedelta(days=period_days)
    snapshot = (
        DataSnapshot.objects.filter(source="slack", period_end__gte=cutoff)
        .order_by("-period_end")
        .first()
    )
    if snapshot is None:
        raise InsufficientData("no Slack snapshot available for requested period")

    metrics = snapshot.metrics or {}
    messages = (metrics.get("messages") or {}).get("data") or {}
    channels = (metrics.get("channels") or {}).get("data") or {}
    users = (metrics.get("users") or {}).get("data") or {}

    per_channel: dict[str, dict[str, int]] = messages.get("per_channel") or {}
    top = sorted(
        ({"name": k, **v} for k, v in per_channel.items()),
        key=lambda c: int(c.get("count", 0) or 0),
        reverse=True,
    )[: SlackActivity.TOP_N]

    total_users = int(users.get("total") or 0)
    bots = int(users.get("bots") or 0)
    bot_ratio = (bots / total_users) if total_users else 0.0

    quality: DataQuality = "high" if total_users and per_channel else "partial"
    return SlackActivity(
        period_days=period_days,
        total_messages=int(messages.get("total_messages") or 0),
        active_users=int(messages.get("active_users") or 0),
        channel_count=int(channels.get("count") or 0),
        top_channels=top,
        bot_ratio=round(bot_ratio, 3),
        data_quality=quality,
    )

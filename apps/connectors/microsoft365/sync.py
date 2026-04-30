"""Microsoft 365 sync — Outlook + Calendar + OneDrive + Teams aggregates."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.microsoft365.client import Microsoft365Client
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    senders: Counter[str] = Counter()
    unread = 0
    for m in messages:
        sender = ((m.get("from") or {}).get("emailAddress") or {}).get("address") or ""
        if sender:
            senders[sender] += 1
        if not m.get("isRead", True):
            unread += 1
    return {
        "total": len(messages),
        "unread": unread,
        "unique_senders": len(senders),
        "top_senders": senders.most_common(5),
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="microsoft365", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with Microsoft365Client(integration) as client:
        try:
            messages = client.list_messages(top=100)
        except Exception as exc:
            logger.exception("MS365 mail listing failed: %s", exc)
            messages = []
        try:
            events = client.list_calendar_events(days=days)
        except Exception as exc:
            logger.warning("MS365 calendar skipped: %s", exc)
            events = []
        try:
            drive = client.list_drive_root(top=50)
        except Exception as exc:
            logger.warning("MS365 onedrive skipped: %s", exc)
            drive = []
        try:
            teams = client.list_joined_teams()
        except Exception as exc:
            logger.warning("MS365 teams skipped: %s", exc)
            teams = []

    snapshot = DataSnapshot.objects.create(
        source="microsoft365",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "mail": {"data": _summarise_messages(messages), "ok": True},
            "calendar": {
                "data": {"upcoming_events": len(events), "window_days": days},
                "ok": True,
            },
            "onedrive": {
                "data": {
                    "root_count": len(drive),
                    "items": [
                        {"name": d.get("name"), "size": d.get("size"), "folder": "folder" in d}
                        for d in drive[:25]
                    ],
                },
                "ok": True,
            },
            "teams": {
                "data": {
                    "count": len(teams),
                    "items": [{"id": t.get("id"), "name": t.get("displayName")} for t in teams[:25]],
                },
                "ok": True,
            },
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

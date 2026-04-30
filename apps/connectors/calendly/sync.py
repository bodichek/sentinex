"""Calendly sync — scheduling load + no-show indicator."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.calendly.client import CalendlyClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: Counter[str] = Counter()
    upcoming = 0
    now = timezone.now()
    for e in events:
        by_status[str(e.get("status") or "unknown")] += 1
        start = e.get("start_time")
        if start:
            try:
                start_dt = timezone.datetime.fromisoformat(start.replace("Z", "+00:00"))
                if start_dt > now:
                    upcoming += 1
            except Exception:
                pass
    return {
        "total": len(events),
        "upcoming": upcoming,
        "by_status": dict(by_status),
    }


def run_sync(days: int = 30) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="calendly", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with CalendlyClient(integration) as client:
        try:
            event_types = client.list_event_types()
            events = client.list_scheduled_events(days_back=days)
        except Exception as exc:
            logger.exception("Calendly sync failed: %s", exc)
            return None

    snapshot = DataSnapshot.objects.create(
        source="calendly",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "event_types": {"data": {"count": len(event_types)}, "ok": True},
            "events": {"data": _summarise_events(events), "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

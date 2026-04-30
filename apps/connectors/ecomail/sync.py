"""Ecomail sync — audience + campaign performance (parallel to SmartEmailing)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.ecomail.client import EcomailClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _aggregate_campaigns(
    client: EcomailClient, campaigns: list[dict[str, Any]], top_n: int = 10
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for c in campaigns[:top_n]:
        cid = c.get("id")
        if cid is None:
            continue
        try:
            stats = client.campaign_stats(int(cid))
        except Exception as exc:
            logger.warning("Ecomail stats fetch failed for campaign %s: %s", cid, exc)
            stats = {}
        enriched.append(
            {
                "id": cid,
                "name": c.get("title") or c.get("name"),
                "sent_at": c.get("sent_at") or c.get("date"),
                "stats": {
                    "delivered": int(stats.get("delivered_emails") or stats.get("delivered") or 0),
                    "opened": int(stats.get("opened_emails") or stats.get("opens") or 0),
                    "clicked": int(stats.get("clicked_emails") or stats.get("clicks") or 0),
                    "bounced": int(stats.get("bounced_emails") or stats.get("bounces") or 0),
                    "unsubscribed": int(
                        stats.get("unsubscribed_emails") or stats.get("unsubscribes") or 0
                    ),
                },
            }
        )
    if not enriched:
        return {"top": [], "open_rate": 0.0, "ctr": 0.0, "delivered": 0}
    delivered = sum(c["stats"]["delivered"] for c in enriched)
    opened = sum(c["stats"]["opened"] for c in enriched)
    clicked = sum(c["stats"]["clicked"] for c in enriched)
    return {
        "top": enriched,
        "open_rate": round((opened / delivered) if delivered else 0.0, 4),
        "ctr": round((clicked / delivered) if delivered else 0.0, 4),
        "delivered": delivered,
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="ecomail", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with EcomailClient(integration) as client:
        try:
            client.ping()
        except Exception as exc:
            logger.warning("Ecomail ping failed: %s", exc)
            return None
        lists_ = client.list_lists()
        campaigns = client.list_campaigns()
        campaigns_summary = _aggregate_campaigns(client, campaigns)

    total_subs = sum(int(l.get("subscribers") or l.get("subscribers_count") or 0) for l in lists_)
    snapshot = DataSnapshot.objects.create(
        source="ecomail",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "audience": {
                "data": {
                    "total_contacts": total_subs,
                    "list_count": len(lists_),
                    "lists": [{"id": l.get("id"), "name": l.get("name")} for l in lists_],
                },
                "ok": True,
            },
            "campaigns": {"data": campaigns_summary, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

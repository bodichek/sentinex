"""SmartEmailing sync — aggregate campaign + audience metrics into DataSnapshot."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.smartemailing.client import SmartEmailingClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _aggregate_campaigns(
    client: SmartEmailingClient, campaigns: list[dict[str, Any]], top_n: int = 10
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for c in campaigns[:top_n]:
        cid = c.get("id")
        if cid is None:
            continue
        try:
            stats = client.campaign_stats(int(cid))
        except Exception as exc:
            logger.warning("SE stats fetch failed for campaign %s: %s", cid, exc)
            stats = {}
        enriched.append(
            {
                "id": cid,
                "name": c.get("name"),
                "sent_at": c.get("sent_at") or c.get("send_at"),
                "stats": {
                    "delivered": stats.get("delivered", 0),
                    "opened": stats.get("opened", 0),
                    "clicked": stats.get("clicked", 0),
                    "bounced": stats.get("bounced", 0),
                    "unsubscribed": stats.get("unsubscribed", 0),
                },
            }
        )
    if not enriched:
        return {"top": [], "open_rate": 0.0, "ctr": 0.0}

    delivered = sum(int(c["stats"].get("delivered") or 0) for c in enriched)
    opened = sum(int(c["stats"].get("opened") or 0) for c in enriched)
    clicked = sum(int(c["stats"].get("clicked") or 0) for c in enriched)
    open_rate = (opened / delivered) if delivered else 0.0
    ctr = (clicked / delivered) if delivered else 0.0
    return {
        "top": enriched,
        "open_rate": round(open_rate, 4),
        "ctr": round(ctr, 4),
        "delivered": delivered,
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(
        provider="smartemailing", is_active=True
    ).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with SmartEmailingClient(integration) as client:
        try:
            client.ping()
        except Exception as exc:
            logger.warning("SmartEmailing ping failed: %s", exc)
            return None

        contactlists = client.list_contactlists()
        total_contacts = client.count_contacts()
        campaigns = client.iter_campaigns()
        campaigns_summary = _aggregate_campaigns(client, campaigns)

    snapshot = DataSnapshot.objects.create(
        source="smartemailing",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "audience": {
                "data": {
                    "total_contacts": total_contacts,
                    "list_count": len(contactlists),
                    "lists": [
                        {"id": cl.get("id"), "name": cl.get("name")} for cl in contactlists
                    ],
                },
                "ok": True,
            },
            "campaigns": {"data": campaigns_summary, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

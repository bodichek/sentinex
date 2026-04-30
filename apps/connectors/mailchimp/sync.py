from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.mailchimp.client import MailchimpClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _aggregate_campaigns(
    client: MailchimpClient, campaigns: list[dict[str, Any]], top_n: int = 10
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for c in campaigns[:top_n]:
        cid = c.get("id")
        if not cid:
            continue
        try:
            r = client.campaign_report(str(cid))
        except Exception as exc:
            logger.warning("Mailchimp report skipped for %s: %s", cid, exc)
            r = {}
        enriched.append(
            {
                "id": cid,
                "name": (c.get("settings") or {}).get("title") or c.get("type"),
                "send_time": c.get("send_time"),
                "stats": {
                    "delivered": int(r.get("emails_sent") or 0)
                    - int((r.get("bounces") or {}).get("hard_bounces") or 0),
                    "opened": int((r.get("opens") or {}).get("opens_total") or 0),
                    "clicked": int((r.get("clicks") or {}).get("clicks_total") or 0),
                    "bounced": int(
                        ((r.get("bounces") or {}).get("hard_bounces") or 0)
                        + ((r.get("bounces") or {}).get("soft_bounces") or 0)
                    ),
                    "unsubscribed": int(r.get("unsubscribed") or 0),
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
    integration = Integration.objects.filter(provider="mailchimp", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with MailchimpClient(integration) as client:
        try:
            client.ping()
        except Exception as exc:
            logger.warning("Mailchimp ping failed: %s", exc)
            return None
        audiences = client.list_audiences()
        campaigns = client.list_campaigns()
        campaigns_summary = _aggregate_campaigns(client, campaigns)

    total_members = sum(int((a.get("stats") or {}).get("member_count") or 0) for a in audiences)
    snapshot = DataSnapshot.objects.create(
        source="mailchimp",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "audience": {
                "data": {
                    "total_contacts": total_members,
                    "list_count": len(audiences),
                    "lists": [{"id": a.get("id"), "name": a.get("name")} for a in audiences],
                },
                "ok": True,
            },
            "campaigns": {"data": campaigns_summary, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

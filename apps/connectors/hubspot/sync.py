"""HubSpot sync — pipeline + deal aggregates (parallel to Pipedrive / Salesforce)."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.hubspot.client import HubspotClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_deals(deals: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_status: Counter[str] = Counter()
    total_amount = 0.0
    won_amount = 0.0
    open_count = 0
    for d in deals:
        props = d.get("properties") or {}
        stage = str(props.get("dealstage") or "unknown")
        amount = float(props.get("amount") or 0)
        is_closed = str(props.get("hs_is_closed", "false")).lower() == "true"
        is_won = str(props.get("hs_is_closed_won", "false")).lower() == "true"
        status = "won" if is_won else ("lost" if is_closed else "open")
        by_status[status] += 1
        bucket = by_stage[stage]
        bucket["count"] += 1
        bucket["amount"] += amount
        total_amount += amount
        if status == "won":
            won_amount += amount
        if status == "open":
            open_count += 1
    return {
        "total": len(deals),
        "open": open_count,
        "by_status": dict(by_status),
        "by_stage": {k: {"count": v["count"], "amount": round(v["amount"], 2)} for k, v in by_stage.items()},
        "total_amount": round(total_amount, 2),
        "won_amount": round(won_amount, 2),
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="hubspot", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with HubspotClient(integration) as client:
        try:
            pipelines = client.list_pipelines()
            deals = client.list_deals()
            contacts_n = len(client.list_contacts(limit=100))  # cheap probe
            companies_n = len(client.list_companies(limit=100))
        except Exception as exc:
            logger.exception("HubSpot sync failed: %s", exc)
            return None

    snapshot = DataSnapshot.objects.create(
        source="hubspot",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "pipelines": {
                "data": [
                    {
                        "id": p.get("id"),
                        "label": p.get("label"),
                        "stages": [
                            {"id": s.get("id"), "label": s.get("label")}
                            for s in (p.get("stages") or [])
                        ],
                    }
                    for p in pipelines
                ],
                "ok": True,
            },
            "deals": {"data": _summarise_deals(deals), "ok": True},
            "contacts": {"data": {"sample_count": contacts_n}, "ok": True},
            "companies": {"data": {"sample_count": companies_n}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

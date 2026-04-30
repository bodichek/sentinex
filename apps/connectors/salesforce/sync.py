"""Salesforce sync — pipeline + deal aggregates (parallel to Pipedrive / HubSpot)."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.salesforce.client import SalesforceClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_opps(opps: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    by_status: Counter[str] = Counter()
    total_amount = 0.0
    won_amount = 0.0
    open_count = 0
    for o in opps:
        stage = str(o.get("StageName") or "Unknown")
        amount = float(o.get("Amount") or 0)
        status = "won" if o.get("IsWon") else ("lost" if o.get("IsClosed") else "open")
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
        "total": len(opps),
        "open": open_count,
        "by_status": dict(by_status),
        "by_stage": {k: {"count": v["count"], "amount": round(v["amount"], 2)} for k, v in by_stage.items()},
        "total_amount": round(total_amount, 2),
        "won_amount": round(won_amount, 2),
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="salesforce", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with SalesforceClient(integration) as client:
        try:
            accounts = client.list_accounts(limit=1)
            opps = client.list_opportunities(limit=2000)
            leads = client.list_leads(limit=1)
            users = client.list_users(limit=1)
        except Exception as exc:
            logger.exception("Salesforce sync failed: %s", exc)
            return None

    opp_records = list(opps.get("records") or [])
    snapshot = DataSnapshot.objects.create(
        source="salesforce",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "accounts": {"data": {"total": int(accounts.get("totalSize") or 0)}, "ok": True},
            "opportunities": {"data": _summarise_opps(opp_records), "ok": True},
            "leads": {"data": {"total": int(leads.get("totalSize") or 0)}, "ok": True},
            "users": {"data": {"total": int(users.get("totalSize") or 0)}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

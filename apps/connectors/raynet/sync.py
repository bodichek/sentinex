"""Raynet CRM sync — emits aggregated CRM metrics into DataSnapshot."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.raynet.client import RaynetClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_business_cases(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_state: Counter[str] = Counter()
    total_value = 0.0
    won_value = 0.0
    open_count = 0
    for it in items:
        state = str(it.get("state") or "OPEN")
        by_state[state] += 1
        value = float(it.get("priceMain") or 0)
        total_value += value
        if state == "WON":
            won_value += value
        if state == "OPEN":
            open_count += 1
    return {
        "total": len(items),
        "open": open_count,
        "by_state": dict(by_state),
        "total_value": round(total_value, 2),
        "won_value": round(won_value, 2),
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="raynet", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with RaynetClient(integration) as client:
        try:
            companies = client.list_companies(limit=1)
            leads = client.list_leads(limit=1)
            cases_resp = client.list_business_cases(limit=500)
            invoices_resp = client.list_invoices(limit=500)
        except Exception as exc:
            logger.exception("Raynet sync failed: %s", exc)
            return None

    cases_data = cases_resp.get("data") or []
    invoices_data = invoices_resp.get("data") or []

    snapshot = DataSnapshot.objects.create(
        source="raynet",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "companies": {"data": {"total": int(companies.get("totalCount") or 0)}, "ok": True},
            "leads": {"data": {"total": int(leads.get("totalCount") or 0)}, "ok": True},
            "business_cases": {"data": _summarise_business_cases(cases_data), "ok": True},
            "invoices": {"data": {"total": len(invoices_data)}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

"""FAPI sync — invoice + revenue aggregates (revenue signal for finance specialist)."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.fapi.client import FapiClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_invoices(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: Counter[str] = Counter()
    total = 0.0
    paid = 0.0
    for inv in invoices:
        status = str(inv.get("paid_status") or inv.get("status") or "open")
        by_status[status] += 1
        amount = float(inv.get("price_total_with_vat") or inv.get("amount") or 0)
        total += amount
        if status in {"paid", "Zaplaceno", "Paid"}:
            paid += amount
    return {
        "count": len(invoices),
        "by_status": dict(by_status),
        "total_with_vat": round(total, 2),
        "paid_with_vat": round(paid, 2),
    }


def _items_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return list(payload.get("items") or payload.get("data") or [])
    return []


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="fapi", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with FapiClient(integration) as client:
        try:
            invoices_raw = client.list_invoices(limit=500)
            clients_raw = client.list_clients(limit=1)
            vouchers_raw = client.list_vouchers(limit=100)
        except Exception as exc:
            logger.exception("FAPI sync failed: %s", exc)
            return None

    invoices = _items_list(invoices_raw)
    vouchers = _items_list(vouchers_raw)

    snapshot = DataSnapshot.objects.create(
        source="fapi",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "invoices": {"data": _summarise_invoices(invoices), "ok": True},
            "clients": {
                "data": {
                    "total": int(
                        clients_raw.get("count")
                        if isinstance(clients_raw, dict)
                        else len(_items_list(clients_raw))
                    )
                },
                "ok": True,
            },
            "vouchers": {"data": {"count": len(vouchers)}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

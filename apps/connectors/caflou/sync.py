"""Caflou sync — companies / projects / tasks / invoices."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.caflou.client import CaflouClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _count(payload: Any) -> int:
    if isinstance(payload, dict):
        for k in ("total", "totalCount", "meta"):
            v = payload.get(k)
            if isinstance(v, int):
                return v
            if isinstance(v, dict):
                t = v.get("total") or v.get("totalCount")
                if isinstance(t, int):
                    return t
        data = payload.get("data") or payload.get("items")
        if isinstance(data, list):
            return len(data)
    if isinstance(payload, list):
        return len(payload)
    return 0


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="caflou", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with CaflouClient(integration) as client:
        try:
            companies = client.list_companies(per_page=1)
            projects = client.list_projects(per_page=1)
            tasks = client.list_tasks(per_page=1)
            invoices = client.list_invoices(per_page=1)
            timesheets = client.list_timesheets(per_page=1)
        except Exception as exc:
            logger.exception("Caflou sync failed: %s", exc)
            return None

    snapshot = DataSnapshot.objects.create(
        source="caflou",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "companies": {"data": {"total": _count(companies)}, "ok": True},
            "projects": {"data": {"total": _count(projects)}, "ok": True},
            "tasks": {"data": {"total": _count(tasks)}, "ok": True},
            "invoices": {"data": {"total": _count(invoices)}, "ok": True},
            "timesheets": {"data": {"total": _count(timesheets)}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

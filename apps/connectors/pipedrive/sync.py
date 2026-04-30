"""Pipedrive sync — pipeline velocity, stage distribution, activity volume."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.pipedrive.client import PipedriveClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_deals(deals: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: Counter[str] = Counter()
    by_stage: dict[int, dict[str, Any]] = defaultdict(lambda: {"count": 0, "value": 0.0})
    total_value = 0.0
    won_value = 0.0
    open_count = 0
    for d in deals:
        status = str(d.get("status") or "open")
        by_status[status] += 1
        stage_id = d.get("stage_id")
        value = float(d.get("value") or 0)
        total_value += value
        if status == "won":
            won_value += value
        if status == "open":
            open_count += 1
        if stage_id is not None:
            bucket = by_stage[int(stage_id)]
            bucket["count"] += 1
            bucket["value"] += value

    return {
        "total": len(deals),
        "open": open_count,
        "by_status": dict(by_status),
        "by_stage": {str(k): v for k, v in by_stage.items()},
        "total_value": round(total_value, 2),
        "won_value": round(won_value, 2),
    }


def _summarise_activities(activities: list[dict[str, Any]]) -> dict[str, Any]:
    types: Counter[str] = Counter()
    done = 0
    for a in activities:
        types[str(a.get("type") or "unknown")] += 1
        if a.get("done"):
            done += 1
    return {
        "total": len(activities),
        "done": done,
        "open": len(activities) - done,
        "by_type": dict(types),
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="pipedrive", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with PipedriveClient(integration) as client:
        try:
            pipelines = client.list_pipelines()
            stages = client.list_stages()
            deals = client.iter_deals()
            persons = client.iter_persons()
            activities = client.iter_activities(days=max(days, 30))
        except Exception as exc:
            logger.exception("Pipedrive sync failed: %s", exc)
            return None

    snapshot = DataSnapshot.objects.create(
        source="pipedrive",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "pipelines": {
                "data": [{"id": p.get("id"), "name": p.get("name")} for p in pipelines],
                "ok": True,
            },
            "stages": {
                "data": [
                    {"id": s.get("id"), "name": s.get("name"), "pipeline_id": s.get("pipeline_id")}
                    for s in stages
                ],
                "ok": True,
            },
            "deals": {"data": _summarise_deals(deals), "ok": True},
            "persons": {"data": {"total": len(persons)}, "ok": True},
            "activities": {"data": _summarise_activities(activities), "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

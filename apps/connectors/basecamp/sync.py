from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.basecamp.client import BasecampClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="basecamp", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with BasecampClient(integration) as client:
        try:
            projects = client.list_projects()
        except Exception as exc:
            logger.exception("Basecamp sync failed: %s", exc)
            return None

    active = [p for p in projects if p.get("status") == "active"]
    snapshot = DataSnapshot.objects.create(
        source="basecamp",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "projects": {
                "data": {
                    "total": len(projects),
                    "active": len(active),
                    "items": [
                        {"id": p.get("id"), "name": p.get("name"), "status": p.get("status")}
                        for p in projects[:25]
                    ],
                },
                "ok": True,
            },
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

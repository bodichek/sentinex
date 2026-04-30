"""Jira sync — issue throughput per project (recently created / updated)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.jira.client import JiraClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="jira", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with JiraClient(integration) as client:
        try:
            projects = client.list_projects()
            jql_recent = f"updated >= -{days}d ORDER BY updated DESC"
            recent = client.search(jql_recent, max_results=200)
            jql_open = "statusCategory != Done"
            open_issues = client.search(jql_open, max_results=1)
            jql_done = f"statusCategory = Done AND resolved >= -{days}d"
            done_issues = client.search(jql_done, max_results=1)
        except Exception as exc:
            logger.exception("Jira sync failed: %s", exc)
            return None

    issues = list(recent.get("issues") or [])

    snapshot = DataSnapshot.objects.create(
        source="jira",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "projects": {
                "data": {
                    "count": len(projects),
                    "items": [
                        {"key": p.get("key"), "name": p.get("name")}
                        for p in projects[:25]
                    ],
                },
                "ok": True,
            },
            "issues": {
                "data": {
                    "recently_updated": int(recent.get("total") or 0),
                    "open_total": int(open_issues.get("total") or 0),
                    "done_window": int(done_issues.get("total") or 0),
                    "window_days": days,
                    "sample": [
                        {
                            "key": i.get("key"),
                            "summary": (i.get("fields") or {}).get("summary"),
                            "status": ((i.get("fields") or {}).get("status") or {}).get("name"),
                        }
                        for i in issues[:20]
                    ],
                },
                "ok": True,
            },
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

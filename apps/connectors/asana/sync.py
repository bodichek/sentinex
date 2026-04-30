"""Asana sync — workspaces / projects / task throughput."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.asana.client import AsanaClient
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _summarise_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    completed = sum(1 for t in tasks if t.get("completed"))
    overdue = 0
    today = timezone.now().date()
    for t in tasks:
        due = t.get("due_on")
        if due and not t.get("completed"):
            try:
                due_d = timezone.datetime.fromisoformat(due).date()
                if due_d < today:
                    overdue += 1
            except Exception:
                pass
    return {
        "total": len(tasks),
        "completed": completed,
        "open": len(tasks) - completed,
        "overdue": overdue,
    }


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="asana", is_active=True).first()
    if integration is None:
        return None

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    with AsanaClient(integration) as client:
        try:
            workspaces = client.list_workspaces()
        except Exception as exc:
            logger.exception("Asana workspaces listing failed: %s", exc)
            return None
        per_project: list[dict[str, Any]] = []
        all_tasks: list[dict[str, Any]] = []
        for ws in workspaces[:5]:
            ws_gid = ws.get("gid")
            if not ws_gid:
                continue
            try:
                projects = client.list_projects(ws_gid, limit=50)
            except Exception as exc:
                logger.warning("Asana projects skipped (%s): %s", ws_gid, exc)
                continue
            for p in projects[:25]:
                p_gid = p.get("gid")
                if not p_gid:
                    continue
                try:
                    tasks = client.list_tasks(p_gid, limit=100)
                except Exception as exc:
                    logger.warning("Asana tasks skipped (%s): %s", p_gid, exc)
                    continue
                per_project.append(
                    {"gid": p_gid, "name": p.get("name"), "tasks": _summarise_tasks(tasks)}
                )
                all_tasks.extend(tasks)

    snapshot = DataSnapshot.objects.create(
        source="asana",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "workspaces": {"data": {"count": len(workspaces)}, "ok": True},
            "projects": {"data": {"count": len(per_project), "items": per_project[:25]}, "ok": True},
            "tasks": {"data": _summarise_tasks(all_tasks), "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot

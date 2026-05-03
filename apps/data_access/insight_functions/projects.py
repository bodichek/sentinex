"""Project / delivery insights — unified across PM connectors.

Reads the most recent ``DataSnapshot`` whose source is one of
``trello`` / ``asana`` / ``jira`` / ``basecamp``. Each PM tool exposes
slightly different metric shapes; we normalise into a single
``ProjectThroughput`` dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot

PM_SOURCES = ("trello", "asana", "jira", "basecamp")


@dataclass(frozen=True)
class ProjectThroughput:
    source: str
    boards: int
    total_items: int  # cards / tasks / issues — whatever the source calls it
    open_items: int
    overdue_items: int
    completed_items: int
    activity_count: int
    active_members: int
    top_boards: list[dict[str, Any]] = field(default_factory=list)
    data_quality: str = "high"


def _extract(source: str, metrics: dict[str, Any]) -> dict[str, Any]:
    if source == "trello":
        boards = (metrics.get("boards") or {}).get("data") or {}
        cards = (metrics.get("cards") or {}).get("data") or {}
        actions = (metrics.get("actions") or {}).get("data") or {}
        items = list(boards.get("items") or [])
        top = sorted(
            items,
            key=lambda b: (b.get("actions") or {}).get("total", 0),
            reverse=True,
        )[:5]
        return {
            "boards": int(boards.get("count") or 0),
            "total": int(cards.get("total") or 0),
            "open": int(cards.get("open") or 0),
            "overdue": int(cards.get("overdue") or 0),
            "completed": int(cards.get("completed") or 0),
            "activity": int(actions.get("total") or 0),
            "active_members": int(actions.get("active_members") or 0),
            "top_boards": [
                {
                    "name": b.get("name"),
                    "url": b.get("url"),
                    "open": (b.get("cards") or {}).get("open", 0),
                    "overdue": (b.get("cards") or {}).get("overdue", 0),
                    "actions": (b.get("actions") or {}).get("total", 0),
                }
                for b in top
            ],
        }
    if source == "asana":
        workspaces = (metrics.get("workspaces") or {}).get("data") or {}
        projects = (metrics.get("projects") or {}).get("data") or {}
        tasks = (metrics.get("tasks") or {}).get("data") or {}
        return {
            "boards": int(projects.get("count") or workspaces.get("count") or 0),
            "total": int(tasks.get("total") or 0),
            "open": int(tasks.get("open") or 0),
            "overdue": int(tasks.get("overdue") or 0),
            "completed": int(tasks.get("completed") or 0),
            "activity": int(tasks.get("total") or 0),
            "active_members": 0,
            "top_boards": [
                {
                    "name": p.get("name"),
                    "open": (p.get("tasks") or {}).get("open", 0),
                    "overdue": (p.get("tasks") or {}).get("overdue", 0),
                    "actions": (p.get("tasks") or {}).get("total", 0),
                }
                for p in (projects.get("items") or [])[:5]
            ],
        }
    if source == "jira":
        projects = (metrics.get("projects") or {}).get("data") or {}
        issues = (metrics.get("issues") or {}).get("data") or {}
        return {
            "boards": int(projects.get("count") or 0),
            "total": int(issues.get("recently_updated") or 0)
            + int(issues.get("open_total") or 0),
            "open": int(issues.get("open_total") or 0),
            "overdue": 0,
            "completed": int(issues.get("done_window") or 0),
            "activity": int(issues.get("recently_updated") or 0),
            "active_members": 0,
            "top_boards": [
                {"name": p.get("name"), "key": p.get("key")}
                for p in (projects.get("items") or [])[:5]
            ],
        }
    if source == "basecamp":
        projects = (metrics.get("projects") or {}).get("data") or {}
        items = list(projects.get("items") or [])
        return {
            "boards": int(projects.get("total") or 0),
            "total": 0,
            "open": int(projects.get("active") or 0),
            "overdue": 0,
            "completed": 0,
            "activity": 0,
            "active_members": 0,
            "top_boards": [
                {"name": p.get("name"), "status": p.get("status")} for p in items[:5]
            ],
        }
    return {}


def get_project_throughput(period_days: int = 7) -> ProjectThroughput:
    snapshot = (
        DataSnapshot.objects.filter(source__in=PM_SOURCES)
        .order_by("-period_end")
        .first()
    )
    if snapshot is None:
        raise InsufficientData(
            "No project-management snapshot available yet. Connect Trello, "
            "Asana, Jira or Basecamp to populate this card."
        )

    fields = _extract(snapshot.source, snapshot.metrics or {})
    if not fields:
        raise InsufficientData(f"Unsupported PM source: {snapshot.source}")

    if fields["boards"] == 0:
        quality = "low"
    elif fields["activity"] == 0:
        quality = "partial"
    else:
        quality = "high"

    return ProjectThroughput(
        source=snapshot.source,
        boards=fields["boards"],
        total_items=fields["total"],
        open_items=fields["open"],
        overdue_items=fields["overdue"],
        completed_items=fields["completed"],
        activity_count=fields["activity"],
        active_members=fields["active_members"],
        top_boards=fields["top_boards"],
        data_quality=quality,
    )

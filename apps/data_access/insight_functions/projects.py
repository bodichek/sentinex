"""Project / delivery insights — backed by Trello DataSnapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot


@dataclass(frozen=True)
class ProjectThroughput:
    boards: int
    total_cards: int
    open_cards: int
    overdue_cards: int
    completed_cards: int
    activity_count: int
    active_members: int
    top_boards: list[dict[str, Any]]
    data_quality: str


def get_project_throughput(period_days: int = 7) -> ProjectThroughput:
    """Latest project-management activity snapshot from Trello."""
    snapshot = (
        DataSnapshot.objects.filter(source="trello").order_by("-period_end").first()
    )
    if snapshot is None:
        raise InsufficientData("No Trello snapshot available yet.")

    metrics = snapshot.metrics or {}
    boards = (metrics.get("boards") or {}).get("data") or {}
    cards = (metrics.get("cards") or {}).get("data") or {}
    actions = (metrics.get("actions") or {}).get("data") or {}

    items = list(boards.get("items") or [])
    top = sorted(
        items,
        key=lambda b: (b.get("actions") or {}).get("total", 0),
        reverse=True,
    )[:5]

    if not items:
        quality = "low"
    elif int(actions.get("total") or 0) == 0:
        quality = "partial"
    else:
        quality = "high"

    return ProjectThroughput(
        boards=int(boards.get("count") or 0),
        total_cards=int(cards.get("total") or 0),
        open_cards=int(cards.get("open") or 0),
        overdue_cards=int(cards.get("overdue") or 0),
        completed_cards=int(cards.get("completed") or 0),
        activity_count=int(actions.get("total") or 0),
        active_members=int(actions.get("active_members") or 0),
        top_boards=[
            {
                "name": b.get("name"),
                "url": b.get("url"),
                "open": (b.get("cards") or {}).get("open", 0),
                "overdue": (b.get("cards") or {}).get("overdue", 0),
                "actions": (b.get("actions") or {}).get("total", 0),
            }
            for b in top
        ],
        data_quality=quality,
    )

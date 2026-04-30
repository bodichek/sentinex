"""Sales insights — backed by Pipedrive DataSnapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot


@dataclass(frozen=True)
class PipelineVelocity:
    total_deals: int
    open_deals: int
    won_count: int
    lost_count: int
    win_rate: float
    avg_deal_value_open: float
    total_open_value: float
    total_won_value: float
    activity_completion_rate: float
    by_stage: dict[str, dict[str, Any]] = field(default_factory=dict)
    data_quality: str = "high"


def get_pipeline_velocity(period_days: int = 30) -> PipelineVelocity:
    """Latest pipeline velocity snapshot from Pipedrive.

    Win rate is computed as ``won / (won + lost)``. Activity completion is
    ``done / total`` from the ``activities`` block.
    Raises ``InsufficientData`` when no snapshot exists.
    """
    snapshot = (
        DataSnapshot.objects.filter(source="pipedrive").order_by("-period_end").first()
    )
    if snapshot is None:
        raise InsufficientData("No Pipedrive snapshot available yet.")

    metrics = snapshot.metrics or {}
    deals = (metrics.get("deals") or {}).get("data") or {}
    activities = (metrics.get("activities") or {}).get("data") or {}

    total = int(deals.get("total") or 0)
    open_count = int(deals.get("open") or 0)
    by_status = deals.get("by_status") or {}
    won = int(by_status.get("won") or 0)
    lost = int(by_status.get("lost") or 0)
    decided = won + lost
    win_rate = (won / decided) if decided else 0.0
    total_open_value = float(deals.get("total_value") or 0) - float(
        deals.get("won_value") or 0
    )
    avg_open = (total_open_value / open_count) if open_count else 0.0

    a_total = int(activities.get("total") or 0)
    a_done = int(activities.get("done") or 0)
    completion = (a_done / a_total) if a_total else 0.0

    if total == 0:
        quality = "low"
    elif decided == 0 or a_total == 0:
        quality = "partial"
    else:
        quality = "high"

    return PipelineVelocity(
        total_deals=total,
        open_deals=open_count,
        won_count=won,
        lost_count=lost,
        win_rate=round(win_rate, 4),
        avg_deal_value_open=round(avg_open, 2),
        total_open_value=round(total_open_value, 2),
        total_won_value=round(float(deals.get("won_value") or 0), 2),
        activity_completion_rate=round(completion, 4),
        by_stage=dict(deals.get("by_stage") or {}),
        data_quality=quality,
    )

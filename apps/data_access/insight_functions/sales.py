"""Sales insights — unified across CRM connectors.

Reads the most recent ``DataSnapshot`` whose source is one of
``pipedrive`` / ``hubspot`` / ``salesforce`` / ``raynet``. Each CRM
sync emits its data under a slightly different key ("deals" vs
"opportunities" vs "business_cases"; "by_status" vs "by_state";
"total_value" vs "total_amount"), so this layer normalises into a
single ``PipelineVelocity`` dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot

CRM_SOURCES = ("pipedrive", "hubspot", "salesforce", "raynet")


@dataclass(frozen=True)
class PipelineVelocity:
    source: str
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


def _extract(source: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Normalise raw snapshot metrics into a common shape."""
    if source == "pipedrive":
        deals = (metrics.get("deals") or {}).get("data") or {}
        activities = (metrics.get("activities") or {}).get("data") or {}
        by_status = deals.get("by_status") or {}
        return {
            "total": int(deals.get("total") or 0),
            "open": int(deals.get("open") or 0),
            "won": int(by_status.get("won") or 0),
            "lost": int(by_status.get("lost") or 0),
            "by_stage": deals.get("by_stage") or {},
            "total_value": float(deals.get("total_value") or 0),
            "won_value": float(deals.get("won_value") or 0),
            "activities_total": int(activities.get("total") or 0),
            "activities_done": int(activities.get("done") or 0),
        }
    if source == "hubspot":
        deals = (metrics.get("deals") or {}).get("data") or {}
        by_status = deals.get("by_status") or {}
        return {
            "total": int(deals.get("total") or 0),
            "open": int(deals.get("open") or 0),
            "won": int(by_status.get("won") or 0),
            "lost": int(by_status.get("lost") or 0),
            "by_stage": deals.get("by_stage") or {},
            "total_value": float(deals.get("total_amount") or 0),
            "won_value": float(deals.get("won_amount") or 0),
            "activities_total": 0,
            "activities_done": 0,
        }
    if source == "salesforce":
        opps = (metrics.get("opportunities") or {}).get("data") or {}
        by_status = opps.get("by_status") or {}
        return {
            "total": int(opps.get("total") or 0),
            "open": int(opps.get("open") or 0),
            "won": int(by_status.get("won") or 0),
            "lost": int(by_status.get("lost") or 0),
            "by_stage": opps.get("by_stage") or {},
            "total_value": float(opps.get("total_amount") or 0),
            "won_value": float(opps.get("won_amount") or 0),
            "activities_total": 0,
            "activities_done": 0,
        }
    if source == "raynet":
        cases = (metrics.get("business_cases") or {}).get("data") or {}
        by_state = cases.get("by_state") or {}
        return {
            "total": int(cases.get("total") or 0),
            "open": int(cases.get("open") or 0),
            "won": int(by_state.get("WON") or 0),
            "lost": int(by_state.get("LOST") or 0),
            "by_stage": {},
            "total_value": float(cases.get("total_value") or 0),
            "won_value": float(cases.get("won_value") or 0),
            "activities_total": 0,
            "activities_done": 0,
        }
    return {}


def get_pipeline_velocity(period_days: int = 30) -> PipelineVelocity:
    snapshot = (
        DataSnapshot.objects.filter(source__in=CRM_SOURCES)
        .order_by("-period_end")
        .first()
    )
    if snapshot is None:
        raise InsufficientData(
            "No CRM snapshot available yet. Connect Pipedrive, HubSpot, "
            "Salesforce or Raynet to populate this card."
        )

    fields = _extract(snapshot.source, snapshot.metrics or {})
    if not fields:
        raise InsufficientData(f"Unsupported CRM source: {snapshot.source}")

    won = fields["won"]
    lost = fields["lost"]
    decided = won + lost
    win_rate = (won / decided) if decided else 0.0
    open_value = max(0.0, fields["total_value"] - fields["won_value"])
    avg_open = (open_value / fields["open"]) if fields["open"] else 0.0
    a_total = fields["activities_total"]
    a_done = fields["activities_done"]
    completion = (a_done / a_total) if a_total else 0.0

    if fields["total"] == 0:
        quality = "low"
    elif decided == 0:
        quality = "partial"
    else:
        quality = "high"

    return PipelineVelocity(
        source=snapshot.source,
        total_deals=fields["total"],
        open_deals=fields["open"],
        won_count=won,
        lost_count=lost,
        win_rate=round(win_rate, 4),
        avg_deal_value_open=round(avg_open, 2),
        total_open_value=round(open_value, 2),
        total_won_value=round(fields["won_value"], 2),
        activity_completion_rate=round(completion, 4),
        by_stage=fields["by_stage"],
        data_quality=quality,
    )

"""Marketing insights — backed by SmartEmailing DataSnapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot


@dataclass(frozen=True)
class MarketingFunnel:
    total_contacts: int
    list_count: int
    delivered: int
    open_rate: float
    ctr: float
    top_campaigns: list[dict[str, Any]] = field(default_factory=list)
    data_quality: str = "high"  # "high" | "partial" | "low"


def get_marketing_funnel(period_days: int = 30) -> MarketingFunnel:
    """Latest aggregated email-marketing performance from SmartEmailing.

    Reads the most recent ``DataSnapshot(source="smartemailing")``. Raises
    ``InsufficientData`` when no snapshot exists.
    """
    snapshot = (
        DataSnapshot.objects.filter(source="smartemailing")
        .order_by("-period_end")
        .first()
    )
    if snapshot is None:
        raise InsufficientData("No SmartEmailing snapshot available yet.")

    metrics = snapshot.metrics or {}
    audience = (metrics.get("audience") or {}).get("data") or {}
    campaigns = (metrics.get("campaigns") or {}).get("data") or {}

    total_contacts = int(audience.get("total_contacts") or 0)
    list_count = int(audience.get("list_count") or 0)
    delivered = int(campaigns.get("delivered") or 0)
    open_rate = float(campaigns.get("open_rate") or 0.0)
    ctr = float(campaigns.get("ctr") or 0.0)
    top = list(campaigns.get("top") or [])

    if total_contacts == 0 and delivered == 0:
        quality = "low"
    elif delivered == 0 or not top:
        quality = "partial"
    else:
        quality = "high"

    return MarketingFunnel(
        total_contacts=total_contacts,
        list_count=list_count,
        delivered=delivered,
        open_rate=open_rate,
        ctr=ctr,
        top_campaigns=top[:5],
        data_quality=quality,
    )

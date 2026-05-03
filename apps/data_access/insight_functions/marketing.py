"""Marketing insights — unified across all e-mail marketing sources.

Reads the most recent ``DataSnapshot`` whose source is one of
``smartemailing``, ``ecomail`` or ``mailchimp``. The three connectors
already write a parallel shape (``audience.total_contacts / list_count``
+ ``campaigns.top / open_rate / ctr / delivered``), so this insight
just picks the freshest snapshot, surfaces the source name and presents
the data uniformly to the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot

MARKETING_SOURCES = ("smartemailing", "ecomail", "mailchimp")


@dataclass(frozen=True)
class MarketingFunnel:
    source: str
    total_contacts: int
    list_count: int
    delivered: int
    open_rate: float
    ctr: float
    top_campaigns: list[dict[str, Any]] = field(default_factory=list)
    data_quality: str = "high"


def get_marketing_funnel(period_days: int = 30) -> MarketingFunnel:
    """Latest aggregated email-marketing performance, source-agnostic."""
    snapshot = (
        DataSnapshot.objects.filter(source__in=MARKETING_SOURCES)
        .order_by("-period_end")
        .first()
    )
    if snapshot is None:
        raise InsufficientData(
            "No e-mail marketing snapshot available yet. Connect "
            "SmartEmailing / Ecomail / Mailchimp to populate this card."
        )

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
        source=snapshot.source,
        total_contacts=total_contacts,
        list_count=list_count,
        delivered=delivered,
        open_rate=open_rate,
        ctr=ctr,
        top_campaigns=top[:5],
        data_quality=quality,
    )

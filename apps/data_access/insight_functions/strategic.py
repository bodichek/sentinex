"""Strategic Insight Functions."""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from django.utils import timezone

from apps.core.cache import cache_result
from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.insight_functions.types.strategic import Anomaly, DataQuality, WeeklyMetrics
from apps.data_access.models import DataSnapshot, ManualKPI


@cache_result(ttl=3600, key_prefix="weekly_metrics")
def get_weekly_metrics() -> WeeklyMetrics:
    """Aggregate the past 7 days of synced metrics + current manual KPIs."""
    today: date = timezone.now().date()
    period_start = today - timedelta(days=7)

    snapshots = list(
        DataSnapshot.objects.filter(period_end__gte=period_start).order_by("-period_end")
    )
    latest_gw = next((s for s in snapshots if s.source == "google_workspace"), None)

    email_count = _metric(latest_gw, "email", "count") if latest_gw else 0
    calendar_events = _metric(latest_gw, "calendar", "count") if latest_gw else 0
    drive_changes = _metric(latest_gw, "drive", "count") if latest_gw else 0

    kpis: dict[str, float] = {}
    for name in ("revenue", "cash_on_hand", "monthly_expenses"):
        kpi = ManualKPI.objects.filter(name=name).order_by("-period_end").first()
        if kpi is not None:
            kpis[name] = float(kpi.value)

    has_any = latest_gw is not None or kpis
    if not has_any:
        raise InsufficientData("no snapshots or manual KPIs available")

    quality: DataQuality = "high" if (latest_gw is not None and len(kpis) >= 2) else "partial"
    return WeeklyMetrics(
        period_start=period_start,
        period_end=today,
        email_count=email_count,
        calendar_events=calendar_events,
        drive_changes=drive_changes,
        manual_kpis=kpis,
        data_quality=quality,
    )


@cache_result(ttl=3600, key_prefix="recent_anomalies")
def get_recent_anomalies(period_days: int = 14) -> list[Anomaly]:
    """Z-score anomaly detection on daily email_count from DataSnapshot metrics."""
    cutoff = timezone.now().date() - timedelta(days=period_days)
    series = list(
        DataSnapshot.objects.filter(
            source="google_workspace", period_end__gte=cutoff
        ).order_by("period_end")
    )
    if len(series) < 5:
        return []

    observations: list[tuple[date, float]] = []
    for s in series:
        value = _metric(s, "email", "count")
        observations.append((s.period_end, float(value)))

    values = [v for _, v in observations]
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) or 1.0

    anomalies: list[Anomaly] = []
    for day, v in observations:
        z = (v - mean) / stdev
        if abs(z) >= 2.0:
            anomalies.append(
                Anomaly(
                    source="google_workspace",
                    metric="email_count",
                    observed=v,
                    baseline_mean=mean,
                    baseline_stdev=stdev,
                    z_score=round(z, 2),
                    direction="spike" if z > 0 else "drop",
                    observed_at=day,
                )
            )
    return anomalies


def _metric(snapshot: DataSnapshot | None, section: str, key: str) -> int:
    if snapshot is None:
        return 0
    sec = snapshot.metrics.get(section) or {}
    data = sec.get("data") or {}
    try:
        return int(data.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0

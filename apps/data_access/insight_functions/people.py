"""People Insight Functions."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from django.utils import timezone

from apps.core.cache import cache_result
from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.insight_functions.types.people import Commitment, DataQuality, TeamActivity
from apps.data_access.models import DataSnapshot


@cache_result(ttl=3600, key_prefix="team_activity")
def get_team_activity_summary(period_days: int = 7) -> TeamActivity:
    today: date = timezone.now().date()
    period_start = today - timedelta(days=period_days)

    snap = (
        DataSnapshot.objects.filter(source="google_workspace", period_end__gte=period_start)
        .order_by("-period_end")
        .first()
    )
    if snap is None:
        raise InsufficientData("no Google Workspace snapshot for requested period")

    cal = (snap.metrics.get("calendar") or {}).get("data") or {}
    mail = (snap.metrics.get("email") or {}).get("data") or {}

    events = int(cal.get("count", 0) or 0)
    threads = int(mail.get("thread_count", mail.get("count", 0)) or 0)
    correspondents = int(mail.get("unique_senders", 0) or 0)

    quality: DataQuality = "high" if all([events, threads]) else "partial"
    return TeamActivity(
        period_start=period_start,
        period_end=today,
        calendar_events=events,
        email_threads=threads,
        unique_correspondents=correspondents,
        data_quality=quality,
    )


@cache_result(ttl=600, key_prefix="upcoming_commitments")
def get_upcoming_commitments(days_ahead: int = 7) -> list[Commitment]:
    """Future calendar events within the next ``days_ahead`` days."""
    snap = (
        DataSnapshot.objects.filter(source="google_workspace").order_by("-period_end").first()
    )
    if snap is None:
        return []

    events = (snap.metrics.get("calendar") or {}).get("data", {}).get("upcoming") or []
    horizon = timezone.now() + timedelta(days=days_ahead)

    out: list[Commitment] = []
    for ev in events:
        start = ev.get("start")
        if not start:
            continue
        try:
            dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt > horizon:
            continue
        out.append(Commitment(starts_at=dt, title=str(ev.get("title", "")), source="google_calendar"))
    return out

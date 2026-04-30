"""Periodic sync jobs that pull aggregated metrics from Workspace via DWD.

Drops typed snapshots into ``DataSnapshot`` rows so the Insight Functions can
read them without touching live Google APIs on the request path.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.data_access.mcp.integrations.google_workspace_dwd import (
    calendar_client,
    directory_client,
    gmail_client,
    reports_client,
)
from apps.data_access.models import DataSnapshot

logger = logging.getLogger(__name__)


def sync_directory_users(domain: str) -> dict[str, Any]:
    """Pull every user in the Workspace domain via Admin SDK Directory API."""
    svc = directory_client()
    users: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        resp = (
            svc.users()
            .list(
                domain=domain,
                maxResults=200,
                pageToken=page_token,
                orderBy="email",
            )
            .execute()
        )
        users.extend(resp.get("users", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    today = timezone.now().date()
    snapshot = DataSnapshot.objects.create(
        source="workspace_directory",
        period_start=today,
        period_end=today,
        metrics={
            "total_users": len(users),
            "users": [
                {
                    "primary_email": u.get("primaryEmail"),
                    "name": (u.get("name") or {}).get("fullName"),
                    "is_admin": u.get("isAdmin"),
                    "suspended": u.get("suspended"),
                    "org_unit_path": u.get("orgUnitPath"),
                    "last_login_time": u.get("lastLoginTime"),
                }
                for u in users
            ],
        },
    )
    return {"snapshot_id": snapshot.pk, "users": len(users)}


def sync_user_calendar_week(user_email: str, days: int = 7) -> dict[str, Any]:
    """Count events for ``user_email`` in the last ``days`` days."""
    svc = calendar_client(user_email)
    now = timezone.now()
    time_min = (now - timedelta(days=days)).isoformat()
    resp = (
        svc.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=now.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
        )
        .execute()
    )
    events = resp.get("items", [])
    DataSnapshot.objects.create(
        source="workspace_calendar",
        period_start=(now - timedelta(days=days)).date(),
        period_end=now.date(),
        metrics={
            "user": user_email,
            "event_count": len(events),
            "meeting_minutes": _sum_meeting_minutes(events),
        },
    )
    return {"user": user_email, "events": len(events)}


def sync_admin_audit_logins(days: int = 7) -> dict[str, Any]:
    """Pull login audit events from Admin SDK Reports."""
    svc = reports_client()
    start_time = (timezone.now() - timedelta(days=days)).isoformat()
    resp = (
        svc.activities()
        .list(userKey="all", applicationName="login", startTime=start_time, maxResults=1000)
        .execute()
    )
    items = resp.get("items", [])
    today = timezone.now().date()
    DataSnapshot.objects.create(
        source="workspace_audit_login",
        period_start=today - timedelta(days=days),
        period_end=today,
        metrics={
            "events": len(items),
            "suspicious": sum(1 for it in items if "suspicious" in str(it).lower()),
        },
    )
    return {"events": len(items)}


def sync_user_email_signals(user_email: str, days: int = 7) -> dict[str, Any]:
    """Lightweight Gmail signals: counts only, no message bodies (privacy default)."""
    svc = gmail_client(user_email)
    after_ts = int((timezone.now() - timedelta(days=days)).timestamp())
    profile = svc.users().getProfile(userId="me").execute()
    inbox = (
        svc.users()
        .messages()
        .list(userId="me", q=f"in:inbox after:{after_ts}", maxResults=500)
        .execute()
    )
    sent = (
        svc.users()
        .messages()
        .list(userId="me", q=f"in:sent after:{after_ts}", maxResults=500)
        .execute()
    )
    metrics = {
        "user": user_email,
        "messages_total": profile.get("messagesTotal"),
        "inbox_recent": len(inbox.get("messages", [])),
        "sent_recent": len(sent.get("messages", [])),
    }
    DataSnapshot.objects.create(
        source="workspace_email",
        period_start=date.today() - timedelta(days=days),
        period_end=date.today(),
        metrics=metrics,
    )
    return metrics


def _sum_meeting_minutes(events: list[dict[str, Any]]) -> int:
    """Approximate total meeting minutes from event start/end strings."""
    from datetime import datetime

    total = 0
    for ev in events:
        start = (ev.get("start") or {}).get("dateTime")
        end = (ev.get("end") or {}).get("dateTime")
        if not start or not end:
            continue
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
            total += int((e - s).total_seconds() // 60)
        except Exception:
            continue
    return total

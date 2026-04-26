"""Google Workspace sync pipeline.

Produces a daily ``DataSnapshot`` per tenant summarising email, calendar, and
drive activity. Runs via Celery; see ``apps.data_access.tasks``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.data_access.mcp.gateway import MCPGateway
from apps.data_access.mcp.integrations.google_workspace import GoogleWorkspaceIntegration
from apps.data_access.models import DataSnapshot, Integration


def run_sync(gateway: MCPGateway | None = None, days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(
        provider="google_workspace", is_active=True
    ).first()
    if integration is None:
        return None

    gateway = gateway or MCPGateway({"google_workspace": GoogleWorkspaceIntegration()})
    period_end: date = timezone.now().date()
    period_start: date = period_end - timedelta(days=days)

    metrics: dict[str, Any] = {}
    metrics["email"] = _safe(gateway.call(integration, "gmail.messages.list", {"days": days}))
    metrics["calendar"] = _safe(
        gateway.call(integration, "calendar.events.list", {"days": days})
    )
    metrics["drive"] = _safe(gateway.call(integration, "drive.files.recent", {"days": days}))

    snapshot = DataSnapshot.objects.create(
        source="google_workspace",
        period_start=period_start,
        period_end=period_end,
        metrics=metrics,
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at"])
    return snapshot


def _safe(result: Any) -> Any:
    return {"ok": bool(getattr(result, "ok", False)), "data": getattr(result, "data", None)}

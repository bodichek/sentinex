"""Dropbox sync — tools catalog + light file metadata snapshot."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.dropbox import client as dropbox_client
from apps.data_access.models import Credential, DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _safe_call(access_token: str, tool: str, args: dict[str, Any] | None = None) -> Any:
    try:
        result = dropbox_client.call_tool(access_token, tool, args)
        if result.is_error:
            return None
        return result.first_json()
    except Exception as exc:
        logger.warning("Dropbox tool %s skipped: %s", tool, exc)
        return None


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="dropbox", is_active=True).first()
    if integration is None:
        return None

    credential = Credential.objects.filter(integration=integration).first()
    if credential is None:
        return None
    tokens = credential.get_tokens()
    access_token = tokens.get("access_token", "")
    if not access_token:
        return None

    try:
        tools = dropbox_client.list_tools(access_token)
        integration.meta = {**(integration.meta or {}), "tools": tools}
    except Exception as exc:
        logger.warning("Dropbox list_tools failed: %s", exc)
        tools = (integration.meta or {}).get("tools") or []

    listing = (
        _safe_call(access_token, "files/list_folder", {"path": "", "limit": 100})
        or _safe_call(access_token, "list_folder", {"path": "", "limit": 100})
        or {}
    )
    file_count = 0
    if isinstance(listing, dict):
        entries = listing.get("entries") or []
        file_count = len(entries)

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)
    snapshot = DataSnapshot.objects.create(
        source="dropbox",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "tools": {"data": {"count": len(tools)}, "ok": True},
            "files": {"data": {"root_count": file_count}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at", "meta"])
    return snapshot

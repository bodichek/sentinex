"""Notion sync — workspace tools catalog + lightweight content snapshot."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.notion import client as notion_client
from apps.data_access.models import Credential, DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _safe_call(access_token: str, tool: str, args: dict[str, Any] | None = None) -> Any:
    try:
        result = notion_client.call_tool(access_token, tool, args)
        if result.is_error:
            return None
        return result.first_json()
    except Exception as exc:
        logger.warning("Notion tool %s skipped: %s", tool, exc)
        return None


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="notion", is_active=True).first()
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
        tools = notion_client.list_tools(access_token)
        integration.meta = {**(integration.meta or {}), "tools": tools}
    except Exception as exc:
        logger.warning("Notion list_tools failed: %s", exc)
        tools = (integration.meta or {}).get("tools") or []

    # Try common read tools — name varies by server version, hence the soft-fail loop.
    search_pages = (
        _safe_call(access_token, "search", {"query": ""})
        or _safe_call(access_token, "notion/search", {"query": ""})
        or {}
    )
    page_count = 0
    if isinstance(search_pages, dict):
        page_count = len(search_pages.get("results") or [])
    elif isinstance(search_pages, list):
        page_count = len(search_pages)

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)
    snapshot = DataSnapshot.objects.create(
        source="notion",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "tools": {"data": {"count": len(tools)}, "ok": True},
            "search": {"data": {"page_count": page_count}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at", "meta"])
    return snapshot

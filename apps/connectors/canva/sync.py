"""Canva sync — discover tools + emit aggregated design metrics."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors.canva import client as canva_client
from apps.connectors.canva.integration import _credential, _refresh_and_persist
from apps.data_access.models import DataSnapshot, Integration

logger = logging.getLogger(__name__)


def _safe_call(access_token: str, tool: str, args: dict[str, Any] | None = None) -> Any:
    try:
        result = canva_client.call_tool(access_token, tool, args)
        if result.is_error:
            return None
        return result.first_json()
    except Exception as exc:
        logger.warning("Canva tool %s skipped: %s", tool, exc)
        return None


def run_sync(days: int = 7) -> DataSnapshot | None:
    integration = Integration.objects.filter(provider="canva", is_active=True).first()
    if integration is None:
        return None

    credential = _credential(integration)
    tokens = credential.get_tokens()
    access_token = tokens.get("access_token", "")
    if not access_token:
        return None

    # Refresh tools catalog opportunistically — schemas drift over time.
    try:
        tools = canva_client.list_tools(access_token)
        integration.meta = {**(integration.meta or {}), "tools": tools}
    except Exception as exc:
        logger.warning("Canva list_tools failed: %s", exc)
        tools = (integration.meta or {}).get("tools") or []

    # Conservative: try a handful of read tools by their conventional names.
    # ``_safe_call`` returns None when the tool is missing or errored, which
    # keeps the snapshot resilient to upstream tool renames.
    profile = _safe_call(access_token, "users/me", {})
    designs = _safe_call(access_token, "designs/list", {"limit": 100}) or []
    brand_templates = _safe_call(access_token, "brand-templates/list", {}) or []
    folders = _safe_call(access_token, "folders/list", {}) or []

    if isinstance(designs, dict):
        designs = designs.get("items") or designs.get("designs") or []
    if isinstance(brand_templates, dict):
        brand_templates = (
            brand_templates.get("items") or brand_templates.get("brand_templates") or []
        )
    if isinstance(folders, dict):
        folders = folders.get("items") or folders.get("folders") or []

    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)

    snapshot = DataSnapshot.objects.create(
        source="canva",
        period_start=period_start,
        period_end=period_end,
        metrics={
            "profile": {"data": profile or {}, "ok": profile is not None},
            "designs": {
                "data": {
                    "count": len(designs) if isinstance(designs, list) else 0,
                    "items": designs[:25] if isinstance(designs, list) else [],
                },
                "ok": True,
            },
            "brand_templates": {
                "data": {"count": len(brand_templates) if isinstance(brand_templates, list) else 0},
                "ok": True,
            },
            "folders": {
                "data": {"count": len(folders) if isinstance(folders, list) else 0},
                "ok": True,
            },
            "tools": {"data": {"count": len(tools)}, "ok": True},
        },
    )
    integration.last_sync_at = timezone.now()  # type: ignore[assignment]
    integration.save(update_fields=["last_sync_at", "meta"])

    # Persist refreshed tokens if list_tools forced a refresh upstream.
    new_tokens = credential.get_tokens()
    if new_tokens.get("access_token") != access_token:
        _refresh_and_persist(credential, new_tokens)
    return snapshot

"""Core event bus: Django signals + Celery async dispatch."""

from __future__ import annotations

from typing import Any

import django.dispatch
from celery import shared_task

addon_activated = django.dispatch.Signal()
addon_deactivated = django.dispatch.Signal()
data_synced = django.dispatch.Signal()
report_generated = django.dispatch.Signal()

_REGISTRY = {
    "addon_activated": addon_activated,
    "addon_deactivated": addon_deactivated,
    "data_synced": data_synced,
    "report_generated": report_generated,
}


def dispatch_event(event_name: str, payload: dict[str, Any] | None = None) -> None:
    signal = _REGISTRY.get(event_name)
    if signal is None:
        raise ValueError(f"Unknown event '{event_name}'")
    signal.send(sender="core", **(payload or {}))
    # Also queue async fan-out for cross-process subscribers.
    dispatch_event_async.delay(event_name, payload or {})


@shared_task(name="core.dispatch_event_async")  # type: ignore[untyped-decorator]
def dispatch_event_async(event_name: str, payload: dict[str, Any]) -> None:
    signal = _REGISTRY.get(event_name)
    if signal is None:
        return
    signal.send(sender="core_async", **payload)

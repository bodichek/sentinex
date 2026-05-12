"""Periodic alerting checks against Langfuse."""

from __future__ import annotations

import logging

from celery import shared_task

from apps.observability.langfuse_client import get_client
from apps.observability.signals import high_error_rate

logger = logging.getLogger("sentinex.observability.alerts")

ERROR_RATE_THRESHOLD = 0.10


@shared_task(name="observability.check_error_rate")  # type: ignore[untyped-decorator]
def check_error_rate(window_minutes: int = 30) -> dict[str, float | int]:
    """Pull recent traces from Langfuse and emit a signal when error rate is high."""
    client = get_client()
    sdk = client._get_sdk()  # noqa: SLF001
    if sdk is None:
        return {"enabled": 0, "error_rate": 0.0}

    try:
        from datetime import UTC, datetime, timedelta

        since = datetime.now(UTC) - timedelta(minutes=window_minutes)
        traces = sdk.fetch_traces(from_timestamp=since.isoformat())
        items = list(getattr(traces, "data", []) or [])
    except Exception:  # noqa: BLE001
        logger.exception("failed to fetch traces for error_rate check")
        return {"enabled": 1, "error_rate": 0.0}

    if not items:
        return {"enabled": 1, "error_rate": 0.0, "total": 0}
    errors = sum(1 for t in items if str(getattr(t, "level", "")).upper() == "ERROR")
    rate = errors / len(items)
    if rate >= ERROR_RATE_THRESHOLD:
        high_error_rate.send(sender=check_error_rate, error_rate=rate, total=len(items))
    return {"enabled": 1, "error_rate": round(rate, 4), "total": len(items), "errors": errors}

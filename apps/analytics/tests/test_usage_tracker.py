"""Tests for the billing usage tracker (Redis cache + ClickHouse fallback)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from apps.analytics.schemas import TenantUsageSummary
from apps.billing import usage_tracker


def _summary() -> TenantUsageSummary:
    return TenantUsageSummary(
        tenant_id="t1",
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
        agent_runs=3,
        total_cost_usd=0.5,
    )


def test_usage_tracker_calls_clickhouse_when_cache_disabled() -> None:
    fake_summary = _summary()

    class FakeClient:
        async def get_tenant_usage(self, tenant_id, f, t):  # type: ignore[no-untyped-def]
            return fake_summary

    out = usage_tracker.get_usage(
        "t1", date(2026, 1, 1), date(2026, 1, 31),
        client=FakeClient(),  # type: ignore[arg-type]
        use_cache=False,
    )
    assert out.agent_runs == 3


def test_usage_tracker_uses_redis_cache_on_hit() -> None:
    cached_value = _summary().model_dump_json()
    with patch("apps.billing.usage_tracker.cache") as mock_cache:
        mock_cache.get.return_value = cached_value
        out = usage_tracker.get_usage(
            "t1", date(2026, 1, 1), date(2026, 1, 31),
            client=MagicMock(),  # should not be used
        )
    assert out.agent_runs == 3

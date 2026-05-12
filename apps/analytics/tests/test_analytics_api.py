"""Tests for the analytics REST endpoints."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.analytics.schemas import AgentMetricRow, TenantUsageSummary
from apps.analytics.views import CostsView, RunsView, UsageView


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


def _user() -> object:
    class _U:
        is_authenticated = True
        pk = 1

    return _U()


def test_usage_endpoint_returns_summary(factory: APIRequestFactory) -> None:
    summary = TenantUsageSummary(
        tenant_id="t1",
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
        agent_runs=12,
        total_input_tokens=100,
        total_output_tokens=50,
        total_cost_usd=1.23,
        by_agent_type={"research": 12},
    )

    async def fake_get_tenant_usage(self, *a, **k):  # type: ignore[no-untyped-def]
        return summary

    request = factory.get("/api/v1/analytics/usage/?period=2026-01")
    force_authenticate(request, user=_user())
    with patch(
        "apps.analytics.clickhouse_client.SentinexClickHouseClient.get_tenant_usage",
        new=fake_get_tenant_usage,
    ):
        response = UsageView.as_view()(request)
    assert response.status_code == 200
    assert response.data["agent_runs"] == 12
    assert response.data["by_agent_type"] == {"research": 12}


def test_runs_endpoint_returns_metric_rows(factory: APIRequestFactory) -> None:
    async def fake_metrics(self, *a, **k):  # type: ignore[no-untyped-def]
        return [AgentMetricRow(agent_type="research", runs=5, avg_duration_ms=120.0, failure_rate=0.0, total_cost_usd=0.5)]

    request = factory.get("/api/v1/analytics/runs/?period=7d")
    force_authenticate(request, user=_user())
    with patch(
        "apps.analytics.clickhouse_client.SentinexClickHouseClient.get_agent_metrics",
        new=fake_metrics,
    ):
        response = RunsView.as_view()(request)
    assert response.status_code == 200
    assert response.data["rows"][0]["agent_type"] == "research"


def test_costs_endpoint_returns_breakdown(factory: APIRequestFactory) -> None:
    summary = TenantUsageSummary(
        tenant_id="t1",
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
        total_cost_usd=4.56,
        by_agent_type={"research": 7, "ops": 3},
    )

    async def fake_usage(self, *a, **k):  # type: ignore[no-untyped-def]
        return summary

    request = factory.get("/api/v1/analytics/costs/?period=2026-01")
    force_authenticate(request, user=_user())
    with patch(
        "apps.analytics.clickhouse_client.SentinexClickHouseClient.get_tenant_usage",
        new=fake_usage,
    ):
        response = CostsView.as_view()(request)
    assert response.status_code == 200
    assert response.data["total_cost_usd"] == 4.56
    assert response.data["by_agent_type"] == {"research": 7, "ops": 3}

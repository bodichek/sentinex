"""Insight Function tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django_tenants.utils import schema_context

from apps.data_access.insight_functions import (
    get_cashflow_snapshot,
    get_recent_anomalies,
    get_team_activity_summary,
    get_upcoming_commitments,
    get_weekly_metrics,
)
from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.models import DataSnapshot, ManualKPI


def _clear() -> None:
    cache.clear()
    DataSnapshot.objects.all().delete()
    ManualKPI.objects.all().delete()


@pytest.mark.django_db(transaction=True)
class TestWeeklyMetrics:
    def test_raises_when_no_data(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            with pytest.raises(InsufficientData):
                get_weekly_metrics()

    def test_returns_metrics_with_kpis_only(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            ManualKPI.objects.create(name="revenue", value=Decimal("100000"), period_end=date.today())
            m = get_weekly_metrics()
            assert m.manual_kpis["revenue"] == 100000.0
            assert m.data_quality == "partial"

    def test_cache_hit(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            ManualKPI.objects.create(
                name="cash_on_hand", value=Decimal("500000"), period_end=date.today()
            )
            m1 = get_weekly_metrics()
            ManualKPI.objects.create(
                name="cash_on_hand", value=Decimal("999999"), period_end=date.today()
            )
            m2 = get_weekly_metrics()
            assert m1 == m2


@pytest.mark.django_db(transaction=True)
class TestCashflowSnapshot:
    def test_requires_cash_and_expenses(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            with pytest.raises(InsufficientData):
                get_cashflow_snapshot()

    def test_computes_runway(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            ManualKPI.objects.create(name="cash_on_hand", value=Decimal("1200000"), period_end=date.today())
            ManualKPI.objects.create(name="monthly_expenses", value=Decimal("200000"), period_end=date.today())
            snapshot = get_cashflow_snapshot()
            assert snapshot.cash_on_hand == Decimal("1200000")
            assert snapshot.runway_months == 6.0


@pytest.mark.django_db(transaction=True)
class TestAnomalies:
    def test_empty_series_returns_empty(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            assert get_recent_anomalies() == []

    def test_detects_spike(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            today = date.today()
            for i in range(7, 1, -1):
                DataSnapshot.objects.create(
                    source="google_workspace",
                    period_start=today - timedelta(days=i + 1),
                    period_end=today - timedelta(days=i),
                    metrics={"email": {"data": {"count": 10}}},
                )
            DataSnapshot.objects.create(
                source="google_workspace",
                period_start=today - timedelta(days=1),
                period_end=today,
                metrics={"email": {"data": {"count": 500}}},
            )
            anomalies = get_recent_anomalies()
            assert len(anomalies) >= 1
            assert anomalies[-1].direction == "spike"


@pytest.mark.django_db(transaction=True)
class TestTeamActivity:
    def test_requires_snapshot(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            with pytest.raises(InsufficientData):
                get_team_activity_summary()

    def test_aggregates(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            today = date.today()
            DataSnapshot.objects.create(
                source="google_workspace",
                period_start=today - timedelta(days=7),
                period_end=today,
                metrics={
                    "calendar": {"data": {"count": 12}},
                    "email": {"data": {"thread_count": 40, "unique_senders": 8}},
                },
            )
            t = get_team_activity_summary()
            assert t.calendar_events == 12
            assert t.email_threads == 40


@pytest.mark.django_db(transaction=True)
class TestCommitments:
    def test_no_snapshot_returns_empty(self) -> None:
        with schema_context("test_tenant"):
            _clear()
            assert get_upcoming_commitments() == []

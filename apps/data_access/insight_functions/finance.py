"""Finance Insight Functions."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.core.cache import cache_result
from apps.data_access.insight_functions.exceptions import InsufficientData
from apps.data_access.insight_functions.types.finance import CashflowSnapshot, DataQuality
from apps.data_access.models import ManualKPI


@cache_result(ttl=24 * 3600, key_prefix="cashflow_snapshot")
def get_cashflow_snapshot() -> CashflowSnapshot:
    """Compute runway from most recent manual KPIs (cash, revenue, expenses)."""
    latest = {
        name: ManualKPI.objects.filter(name=name).order_by("-period_end").first()
        for name in ("cash_on_hand", "revenue", "monthly_expenses")
    }

    cash = latest["cash_on_hand"]
    expenses = latest["monthly_expenses"]
    revenue = latest["revenue"]

    if cash is None or expenses is None:
        raise InsufficientData("cash_on_hand and monthly_expenses are required")

    revenue_value = revenue.value if revenue is not None else Decimal("0")
    burn = expenses.value - revenue_value
    runway = float("inf") if burn <= 0 else float(cash.value / burn)

    quality: DataQuality = "high" if revenue is not None else "partial"

    return CashflowSnapshot(
        as_of=timezone.now().date(),
        cash_on_hand=cash.value,
        monthly_revenue=revenue_value,
        monthly_expenses=expenses.value,
        runway_months=round(runway, 2) if runway != float("inf") else runway,
        data_quality=quality,
    )

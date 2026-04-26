"""Finance-domain output types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

DataQuality = Literal["high", "partial", "missing"]


@dataclass(frozen=True)
class CashflowSnapshot:
    as_of: date
    cash_on_hand: Decimal
    monthly_revenue: Decimal
    monthly_expenses: Decimal
    runway_months: float
    data_quality: DataQuality

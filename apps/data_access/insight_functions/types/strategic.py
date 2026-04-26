"""Strategic-domain output types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

DataQuality = Literal["high", "partial", "missing"]

__all__ = ["Anomaly", "DataQuality", "WeeklyMetrics"]


@dataclass(frozen=True)
class WeeklyMetrics:
    period_start: date
    period_end: date
    email_count: int = 0
    calendar_events: int = 0
    drive_changes: int = 0
    manual_kpis: dict[str, float] = field(default_factory=dict)
    data_quality: DataQuality = "partial"


@dataclass(frozen=True)
class Anomaly:
    source: str
    metric: str
    observed: float
    baseline_mean: float
    baseline_stdev: float
    z_score: float
    direction: Literal["spike", "drop"]
    observed_at: date

"""People-domain output types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

DataQuality = Literal["high", "partial", "missing"]


@dataclass(frozen=True)
class TeamActivity:
    period_start: date
    period_end: date
    calendar_events: int
    email_threads: int
    unique_correspondents: int
    data_quality: DataQuality


@dataclass(frozen=True)
class Commitment:
    starts_at: datetime
    title: str
    source: str

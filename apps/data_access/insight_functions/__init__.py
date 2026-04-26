"""Insight Functions registry — the Sentinex data-access moat.

Each function is pure, typed, cached, and tenant-scoped. Specialists and
addons consume these; they never touch raw tables directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.data_access.insight_functions.finance import get_cashflow_snapshot
from apps.data_access.insight_functions.people import (
    get_team_activity_summary,
    get_upcoming_commitments,
)
from apps.data_access.insight_functions.slack import get_slack_activity
from apps.data_access.insight_functions.strategic import (
    get_recent_anomalies,
    get_weekly_metrics,
)

INSIGHT_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "get_weekly_metrics": get_weekly_metrics,
    "get_recent_anomalies": get_recent_anomalies,
    "get_team_activity_summary": get_team_activity_summary,
    "get_upcoming_commitments": get_upcoming_commitments,
    "get_cashflow_snapshot": get_cashflow_snapshot,
    "get_slack_activity": get_slack_activity,
}

__all__ = [
    "INSIGHT_FUNCTIONS",
    "get_cashflow_snapshot",
    "get_recent_anomalies",
    "get_slack_activity",
    "get_team_activity_summary",
    "get_upcoming_commitments",
    "get_weekly_metrics",
]

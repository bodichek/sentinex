"""Build the context object that feeds specialists + orchestrator.

Pulls the tenant identity and attempts to attach Insight Function outputs
so specialists can reason against real data instead of the user query alone.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from django.db import connection

from apps.agents.base import AgentContext
from apps.data_access.insight_functions import INSIGHT_FUNCTIONS
from apps.data_access.insight_functions.exceptions import InsufficientData

logger = logging.getLogger(__name__)

DEFAULT_INSIGHTS = ("get_weekly_metrics", "get_cashflow_snapshot")


def build(query: str, insights: tuple[str, ...] = DEFAULT_INSIGHTS) -> AgentContext:
    schema = getattr(connection, "schema_name", None)
    tenant_obj = getattr(connection, "tenant", None)
    org_summary = getattr(tenant_obj, "name", "") or ""

    insights_payload: dict[str, Any] = {}
    for name in insights:
        func = INSIGHT_FUNCTIONS.get(name)
        if func is None:
            continue
        try:
            result = func()
        except InsufficientData as exc:
            insights_payload[name] = {"error": "insufficient_data", "detail": str(exc)}
        except Exception as exc:
            logger.exception("insight function %s failed", name)
            insights_payload[name] = {"error": "failure", "detail": str(exc)}
        else:
            insights_payload[name] = _serialize(result)

    return AgentContext(
        query=query,
        tenant_schema=schema,
        org_summary=org_summary,
        extra={"insights": insights_payload},
    )


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    return obj

"""Analytics REST API."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar

from django.db import connection
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.clickhouse_client import SentinexClickHouseClient


def _tenant_id(request: Request) -> str:
    tenant = getattr(connection, "tenant", None)
    return str(getattr(tenant, "pk", None) or getattr(tenant, "schema_name", "public"))


def _parse_period(value: str | None) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    if not value:
        return today.replace(day=1), today
    try:
        year, month = (int(p) for p in value.split("-"))
        start = date(year, month, 1)
    except (ValueError, AttributeError):
        return today.replace(day=1), today
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


class UsageView(APIView):
    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        period = request.query_params.get("period")
        f, t = _parse_period(period)
        client = SentinexClickHouseClient()
        try:
            summary = asyncio.run(client.get_tenant_usage(_tenant_id(request), f, t))
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(summary.model_dump(mode="json"))


class RunsView(APIView):
    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        period = request.query_params.get("period", "7d")
        agent_type = request.query_params.get("agent_type")
        client = SentinexClickHouseClient()
        try:
            metrics = asyncio.run(
                client.get_agent_metrics(_tenant_id(request), agent_type, period)
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"period": period, "rows": [m.model_dump() for m in metrics]})


class CostsView(APIView):
    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        period = request.query_params.get("period")
        f, t = _parse_period(period)
        client = SentinexClickHouseClient()
        try:
            summary = asyncio.run(client.get_tenant_usage(_tenant_id(request), f, t))
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        out: dict[str, Any] = {
            "period_from": f.isoformat(),
            "period_to": t.isoformat(),
            "total_cost_usd": summary.total_cost_usd,
            "by_agent_type": summary.by_agent_type,
        }
        return Response(out)

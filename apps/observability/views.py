"""Read endpoints + alerting hook for observability data."""

from __future__ import annotations

from typing import Any, ClassVar

from django.db import connection
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.observability.langfuse_client import get_client


class TracesView(APIView):
    """GET /api/v1/observability/traces/ — list traces for the current tenant."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        client = get_client()
        sdk = client._get_sdk()  # noqa: SLF001
        if sdk is None:
            return Response({"results": [], "detail": "langfuse_disabled"})

        tenant = getattr(connection, "tenant", None)
        tenant_id = str(getattr(tenant, "pk", None) or getattr(tenant, "schema_name", "public"))

        params: dict[str, Any] = {"tags": [f"tenant:{tenant_id}"]}
        if (agent_type := request.query_params.get("agent_type")):
            params["tags"].append(f"agent:{agent_type}")
        if (date_from := request.query_params.get("date_from")):
            params["from_timestamp"] = date_from
        if (date_to := request.query_params.get("date_to")):
            params["to_timestamp"] = date_to

        try:
            traces = sdk.fetch_traces(**params)
        except Exception as exc:  # noqa: BLE001
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        items = []
        for t in getattr(traces, "data", []) or []:
            tid = getattr(t, "id", None)
            items.append(
                {
                    "id": tid,
                    "name": getattr(t, "name", None),
                    "timestamp": str(getattr(t, "timestamp", "")),
                    "url": client.trace_url(tid) if tid else None,
                }
            )
        return Response({"results": items})

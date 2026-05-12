"""API views for the agent layer."""

from __future__ import annotations

from dataclasses import asdict
from typing import ClassVar

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents import context_builder
from apps.agents.orchestrator import Orchestrator
from apps.agents.tasks import run_agent_async


class QueryView(APIView):
    """POST /api/v1/query/ — run a single user query through the orchestrator."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        query = (request.data.get("query") or "").strip()
        if not query:
            return Response(
                {"detail": "query is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        context = context_builder.build(query)
        orchestrator_response = Orchestrator().handle(query, context)

        return Response(
            {
                "intent": asdict(orchestrator_response.intent),
                "final": orchestrator_response.final,
                "specialists": [
                    {
                        "name": s.name,
                        "content": s.content,
                        "structured_data": s.structured_data,
                        "confidence": s.confidence,
                    }
                    for s in orchestrator_response.specialist_responses
                ],
            }
        )


class AgentRunView(APIView):
    """POST /api/v1/agents/{agent_type}/run/ — launch a LangGraph agent run."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def post(self, request: Request, agent_type: str) -> Response:
        from django.db import connection

        body_input = (request.data.get("input") or "").strip()
        session_id = request.data.get("session_id") or "default"
        if not body_input:
            return Response(
                {"detail": "input is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        tenant = getattr(connection, "tenant", None)
        tenant_schema = getattr(tenant, "schema_name", "public")
        tenant_id = str(getattr(tenant, "pk", tenant_schema))

        async_result = run_agent_async.delay(
            agent_type=agent_type,
            tenant_schema=tenant_schema,
            tenant_id=tenant_id,
            session_id=session_id,
            payload={"input": body_input, "metadata": request.data.get("metadata") or {}},
            user_id=getattr(request.user, "pk", None),
        )
        return Response({"run_id": async_result.id, "status": "queued"})

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

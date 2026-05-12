"""REST endpoints for the memory module."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from django.db import connection
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.memory.graphiti_client import TenantGraphitiClient
from apps.memory.models import KnowledgeEpisode


def _tenant_id_from(request: Request) -> str:
    tenant = getattr(connection, "tenant", None)
    return str(getattr(tenant, "pk", None) or getattr(tenant, "schema_name", "public"))


class MemorySearchView(APIView):
    """GET /api/v1/memory/search/?q=...&limit=10 — semantic search the graph."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response({"detail": "q is required"}, status=status.HTTP_400_BAD_REQUEST)
        limit = int(request.query_params.get("limit") or 10)

        client = TenantGraphitiClient()
        edges: list[Any] = asyncio.run(
            client.search(_tenant_id_from(request), query, num_results=limit)
        )
        results = [
            {
                "uuid": getattr(e, "uuid", None),
                "name": getattr(e, "name", None),
                "fact": getattr(e, "fact", None),
                "valid_at": getattr(e, "valid_at", None),
                "invalid_at": getattr(e, "invalid_at", None),
            }
            for e in edges
        ]
        return Response({"results": results})


class MemoryEntitiesView(APIView):
    """GET /api/v1/memory/entities/ — list recent episodes for the tenant."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        episodes = list(
            KnowledgeEpisode.objects.all()[:100].values(
                "id",
                "name",
                "source",
                "reference_time",
                "graphiti_episode_uuid",
            )
        )
        return Response({"episodes": episodes})


class MemoryEpisodeView(APIView):
    """POST /api/v1/memory/episode/ — manually add an episode to the graph."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        content = (request.data.get("content") or "").strip()
        if not content:
            return Response(
                {"detail": "content is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        name = request.data.get("name") or "manual"
        source_description = request.data.get("source_description") or "manual"

        client = TenantGraphitiClient()
        result = asyncio.run(
            client.add_episode(
                _tenant_id_from(request),
                content,
                name=name,
                source_description=source_description,
                metadata=request.data.get("metadata") or {},
            )
        )
        episode_uuid = getattr(getattr(result, "episode", None), "uuid", "") or ""

        from datetime import UTC, datetime

        record = KnowledgeEpisode.objects.create(
            name=name,
            source="message",
            source_description=source_description,
            content=content,
            metadata=request.data.get("metadata") or {},
            graphiti_episode_uuid=episode_uuid,
            user_id=getattr(request.user, "pk", None),
            reference_time=datetime.now(UTC),
        )
        return Response(
            {"id": str(record.id), "graphiti_episode_uuid": episode_uuid},
            status=status.HTTP_201_CREATED,
        )


class MemoryEntityDeleteView(APIView):
    """DELETE /api/v1/memory/entity/{uuid}/ — remove a node from the graph."""

    permission_classes: ClassVar[list[type]] = [IsAuthenticated]

    def delete(self, request: Request, entity_uuid: str) -> Response:
        async def _delete() -> None:
            client = TenantGraphitiClient()
            graph = await client.get_graphiti()
            driver = graph.driver
            async with driver.session() as session:
                await session.run(
                    "MATCH (n {uuid: $uuid}) DETACH DELETE n", uuid=entity_uuid
                )

        asyncio.run(_delete())
        return Response(status=status.HTTP_204_NO_CONTENT)

"""Tenant-scoped Graphiti wrapper.

Uses Anthropic Claude (Haiku) for entity extraction and OpenAI embeddings for
vector lookups (per CLAUDE.md: "Anthropic for LLMs, OpenAI for embeddings only").
Tenant isolation is achieved via Graphiti's ``group_id`` parameter on
``add_episode`` / ``search``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from graphiti_core import Graphiti
    from graphiti_core.edges import EntityEdge
    from graphiti_core.nodes import EpisodeType


_GROUP_SAFE = re.compile(r"[^a-zA-Z0-9_-]")


def _tenant_group_id(tenant_id: str) -> str:
    """Return a Graphiti ``group_id`` derived from a tenant id."""
    return _GROUP_SAFE.sub("_", tenant_id) or "default"


class TenantGraphitiClient:
    """Per-tenant facade around a single shared :class:`Graphiti` instance."""

    def __init__(
        self,
        graphiti: Graphiti | None = None,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._graphiti = graphiti
        self.uri: str = uri or str(getattr(settings, "NEO4J_URI", "bolt://localhost:7687"))
        self.user: str = user or str(getattr(settings, "NEO4J_USER", "neo4j"))
        self.password: str = password or str(getattr(settings, "NEO4J_PASSWORD", ""))

    def _build_clients(self) -> tuple[Any, Any]:
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client.anthropic_client import AnthropicClient
        from graphiti_core.llm_client.config import LLMConfig

        llm = AnthropicClient(
            config=LLMConfig(
                api_key=getattr(settings, "ANTHROPIC_API_KEY", ""),
                model=getattr(
                    settings, "ANTHROPIC_RESEARCH_MODEL", "claude-haiku-4-5-20251001"
                ),
            )
        )
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=getattr(settings, "OPENAI_API_KEY", ""),
                embedding_model=getattr(
                    settings, "KNOWLEDGE_EMBEDDING_MODEL", "text-embedding-3-small"
                ),
            )
        )
        return llm, embedder

    async def get_graphiti(self) -> Graphiti:
        """Return a lazily-initialised, process-shared Graphiti instance."""
        if self._graphiti is None:
            from graphiti_core import Graphiti

            llm, embedder = self._build_clients()
            self._graphiti = Graphiti(
                uri=self.uri,
                user=self.user,
                password=self.password,
                llm_client=llm,
                embedder=embedder,
            )
            await self._graphiti.build_indices_and_constraints()
        return self._graphiti

    async def add_episode(
        self,
        tenant_id: str,
        content: str,
        *,
        name: str = "episode",
        source_description: str = "sentinex",
        source: EpisodeType | None = None,
        metadata: dict[str, Any] | None = None,
        reference_time: datetime | None = None,
    ) -> Any:
        """Add a new episode to the tenant's slice of the knowledge graph."""
        from graphiti_core.nodes import EpisodeType as _EpisodeType

        graph = await self.get_graphiti()
        return await graph.add_episode(
            name=name,
            episode_body=content,
            source_description=source_description,
            reference_time=reference_time or datetime.now(UTC),
            source=source or _EpisodeType.message,
            group_id=_tenant_group_id(tenant_id),
        )

    async def search(
        self,
        tenant_id: str,
        query: str,
        num_results: int = 10,
    ) -> list[EntityEdge]:
        """Run hybrid (semantic + BM25) search scoped to ``tenant_id``."""
        graph = await self.get_graphiti()
        return await graph.search(
            query=query,
            group_ids=[_tenant_group_id(tenant_id)],
            num_results=num_results,
        )

    async def close(self) -> None:
        if self._graphiti is not None:
            await self._graphiti.close()  # type: ignore[no-untyped-call]
            self._graphiti = None

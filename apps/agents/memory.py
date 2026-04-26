"""Memory tiers: Redis short-term, Postgres medium-term, pgvector long-term."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache

from apps.agents.embedding_gateway import embed
from apps.agents.models import (
    Conversation,
    ConversationMessage,
    ExtractedFact,
    MemoryEmbedding,
)

logger = logging.getLogger(__name__)

SHORT_TERM_TTL_SECONDS = 2 * 60 * 60  # 2 hours


@dataclass(frozen=True)
class Turn:
    role: str
    content: str


class ShortTermMemory:
    """Redis-backed rolling window for a single conversation."""

    def __init__(self, conversation_id: str, max_turns: int = 20) -> None:
        self.key = f"stm:{conversation_id}"
        self.max_turns = max_turns

    def append(self, role: str, content: str) -> None:
        turns: list[dict[str, str]] = cache.get(self.key) or []
        turns.append({"role": role, "content": content})
        turns = turns[-self.max_turns :]
        cache.set(self.key, turns, SHORT_TERM_TTL_SECONDS)

    def read(self) -> list[Turn]:
        turns: list[dict[str, str]] = cache.get(self.key) or []
        return [Turn(role=t["role"], content=t["content"]) for t in turns]

    def clear(self) -> None:
        cache.delete(self.key)


class MediumTermMemory:
    """Postgres-backed durable conversation + extracted facts (tenant-scoped)."""

    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    def append_message(self, role: str, content: str, *, masked: bool = False, tokens: int = 0) -> ConversationMessage:
        return ConversationMessage.objects.create(
            conversation=self.conversation,
            role=role,
            content=content,
            masked=masked,
            tokens=tokens,
        )

    def recent_messages(self, limit: int = 20) -> list[ConversationMessage]:
        return list(self.conversation.messages.all()[:limit])

    def record_fact(self, key: str, value: str, *, confidence: float = 1.0, source: str = "") -> ExtractedFact:
        return ExtractedFact.objects.create(
            conversation=self.conversation,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
        )

    def facts(self, key: str | None = None) -> list[ExtractedFact]:
        qs = ExtractedFact.objects.all()
        if key is not None:
            qs = qs.filter(key=key)
        return list(qs)


@dataclass(frozen=True)
class MemoryResult:
    id: str
    content: str
    source: str
    metadata: dict[str, Any]
    distance: float


class LongTermMemory:
    """pgvector-backed RAG store, tenant-scoped via the active DB schema."""

    def index(
        self,
        content: str,
        *,
        source: str = "document",
        metadata: dict[str, Any] | None = None,
        user: Any | None = None,
    ) -> MemoryEmbedding | None:
        """Embed ``content`` and persist a MemoryEmbedding row.

        Returns ``None`` if the embedding gateway / pgvector table isn't
        available (e.g. dev environment without the extension); failures are
        logged but never propagated since indexing is a side-effect of the
        primary operation (saving a brief, snapshot, etc.).
        """
        if not content.strip():
            return None
        try:
            response = embed([content])
        except Exception:
            logger.exception("LongTermMemory: embedding failed")
            return None
        vector = response.vectors[0] if response.vectors else None
        if not vector:
            return None
        try:
            return MemoryEmbedding.objects.create(
                tenant_user=user,
                source=source,
                content=content,
                embedding=vector,
                metadata=metadata or {},
            )
        except Exception:
            logger.exception("LongTermMemory: persist failed")
            return None

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        source_filter: str | None = None,
    ) -> list[MemoryResult]:
        from pgvector.django import CosineDistance

        if not query.strip():
            return []
        try:
            response = embed([query])
        except Exception:
            logger.exception("LongTermMemory: query embedding failed")
            return []
        if not response.vectors:
            return []
        qs = MemoryEmbedding.objects.exclude(embedding=None)
        if source_filter is not None:
            qs = qs.filter(source=source_filter)
        qs = qs.annotate(distance=CosineDistance("embedding", response.vectors[0])).order_by(
            "distance"
        )[:top_k]

        return [
            MemoryResult(
                id=str(row.id),
                content=row.content,
                source=row.source,
                metadata=row.metadata or {},
                distance=float(row.distance),  # type: ignore[attr-defined]
            )
            for row in qs
        ]


class MemoryManager:
    """Aggregate of all memory tiers for a single conversation."""

    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation
        self.short = ShortTermMemory(conversation_id=str(conversation.pk))
        self.medium = MediumTermMemory(conversation=conversation)
        self.long = LongTermMemory()

    def record_turn(self, role: str, content: str, *, masked: bool = False) -> None:
        self.short.append(role, content)
        self.medium.append_message(role, content, masked=masked)

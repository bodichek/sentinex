"""Knowledge embeddings — thin wrapper around the central EmbeddingGateway.

Stub mode (deterministic hash-based vectors) is preserved for offline tests
and pre-API-key dev. All real OpenAI traffic goes through
``apps.agents.embedding_gateway`` for Redis caching, retries, cost accounting,
and structured ``sentinex.llm`` events.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def _stub_embedding(text: str) -> list[float]:
    dim = settings.KNOWLEDGE_EMBEDDING_DIMENSIONS
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        h = hashlib.sha256(f"{text}:{counter}".encode()).digest()
        for byte in h:
            if len(out) >= dim:
                break
            out.append((byte - 128) / 128.0)
        counter += 1
    return out


def _current_tenant() -> Any | None:
    try:
        from django.db import connection

        return connection.get_tenant() if hasattr(connection, "get_tenant") else None
    except Exception:
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for each input text. Uses stub mode when configured."""
    if not texts:
        return []
    if settings.KNOWLEDGE_STUB_MODE or not settings.OPENAI_API_KEY:
        logger.debug("embed_texts: stub mode (n=%d)", len(texts))
        return [_stub_embedding(t) for t in texts]

    from apps.agents.embedding_gateway import embed

    response = embed(
        texts,
        model=settings.KNOWLEDGE_EMBEDDING_MODEL,
        tenant=_current_tenant(),
    )
    expected_dim = settings.KNOWLEDGE_EMBEDDING_DIMENSIONS
    if response.vectors and len(response.vectors[0]) != expected_dim:
        raise RuntimeError(
            f"embedding dimension mismatch: model {settings.KNOWLEDGE_EMBEDDING_MODEL} "
            f"returned {len(response.vectors[0])}, but pgvector column expects {expected_dim}. "
            "Update KNOWLEDGE_EMBEDDING_DIMENSIONS or migration 0005."
        )
    return response.vectors


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]

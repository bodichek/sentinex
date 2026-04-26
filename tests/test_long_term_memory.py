"""Long-term memory + embedding gateway tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import connection
from django_tenants.utils import schema_context


def _pgvector_available() -> bool:
    """Return True iff the running Postgres has the ``vector`` extension."""
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        return cur.fetchone() is not None


@pytest.fixture
def pgvector_or_skip(db: Any) -> None:
    if not _pgvector_available():
        pytest.skip("pgvector extension not installed in the running Postgres")


def _fake_embedding_payload(texts: list[str]) -> Any:
    """Build a deterministic, distinguishable embedding per text."""
    class _Item:
        def __init__(self, vec: list[float]) -> None:
            self.embedding = vec

    class _Resp:
        pass

    items = []
    for i, t in enumerate(texts):
        # Deterministic vector: position i has 1.0, rest 0.0 → orthogonal across texts.
        vec = [0.0] * 1536
        vec[i % 1536] = 1.0
        items.append(_Item(vec))
    resp = _Resp()
    resp.data = items  # type: ignore[attr-defined]
    resp.usage = type("U", (), {"total_tokens": 10 * len(texts)})()  # type: ignore[attr-defined]
    return resp


def test_embed_returns_vector() -> None:
    cache.clear()
    from apps.agents.embedding_gateway import embed

    with patch(
        "apps.agents.embedding_gateway._call_openai",
        side_effect=lambda model, batch: _fake_embedding_payload(batch),
    ):
        result = embed(["hello", "world"], use_cache=False)

    assert len(result.vectors) == 2
    assert all(len(v) == 1536 for v in result.vectors)
    assert result.fetched_count == 2
    assert result.cached_count == 0


def test_embedding_cache_hit() -> None:
    cache.clear()
    from apps.agents.embedding_gateway import embed

    with patch(
        "apps.agents.embedding_gateway._call_openai",
        side_effect=lambda model, batch: _fake_embedding_payload(batch),
    ) as mock_call:
        embed(["repeated text"])
        embed(["repeated text"])
        assert mock_call.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_memory_index_and_search(pgvector_or_skip: None) -> None:
    cache.clear()
    from apps.agents.memory import LongTermMemory

    with (
        patch(
            "apps.agents.embedding_gateway._call_openai",
            side_effect=lambda model, batch: _fake_embedding_payload(batch),
        ),
        schema_context("test_tenant"),
    ):
        mem = LongTermMemory()
        mem.index("doc zero", source="document")
        mem.index("doc one", source="document")
        mem.index("doc two", source="document")

        results = mem.search("doc zero", top_k=3)
        assert len(results) == 3
        # Closest match is the first one indexed (its fake vector matches the query's).
        assert results[0].content == "doc zero"
        assert results[0].distance <= results[-1].distance

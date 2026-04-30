"""Tests for the embedder — focuses on stub mode (no API calls)."""

from __future__ import annotations

from django.conf import settings
from django.test import override_settings

from apps.data_access.knowledge.embedder import embed_query, embed_texts


def reset_client() -> None:
    """No-op: embedder now delegates to embedding_gateway."""
    return None


@override_settings(KNOWLEDGE_STUB_MODE=True)
def test_stub_embeddings_are_deterministic() -> None:
    reset_client()
    a = embed_query("hello")
    b = embed_query("hello")
    assert a == b
    assert len(a) == settings.KNOWLEDGE_EMBEDDING_DIMENSIONS
    assert all(-1.0 <= v <= 1.0 for v in a)


@override_settings(KNOWLEDGE_STUB_MODE=True)
def test_stub_embeddings_differ_across_inputs() -> None:
    reset_client()
    a = embed_query("apple")
    b = embed_query("orange")
    assert a != b


@override_settings(KNOWLEDGE_STUB_MODE=True)
def test_embed_texts_empty_returns_empty() -> None:
    reset_client()
    assert embed_texts([]) == []


@override_settings(KNOWLEDGE_STUB_MODE=True)
def test_embed_texts_one_per_input() -> None:
    reset_client()
    out = embed_texts(["one", "two", "three"])
    assert len(out) == 3
    assert all(len(v) == settings.KNOWLEDGE_EMBEDDING_DIMENSIONS for v in out)

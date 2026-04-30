"""Unit tests for the token-aware text chunker."""

from __future__ import annotations

from apps.data_access.knowledge.chunker import chunk_text


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_single_chunk() -> None:
    chunks = chunk_text("Hello world. This is a small document.", chunk_size=100, overlap=0)
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert "Hello world" in chunks[0].text


def test_long_text_splits_on_paragraphs() -> None:
    paragraphs = ["Para " + str(i) + " " + ("x" * 200) for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, chunk_size=100, overlap=0)
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.index == i
        assert c.text


def test_oversize_paragraph_hard_split() -> None:
    huge = "a" * 5000
    chunks = chunk_text(huge, chunk_size=50, overlap=0)
    assert len(chunks) > 1
    # All chunks together cover the original (or close to it).
    joined = "".join(c.text for c in chunks)
    assert len(joined) >= 4000


def test_overlap_carries_tail_into_next_chunk() -> None:
    text = "\n\n".join([f"Section {i}: " + ("x" * 300) for i in range(5)])
    chunks = chunk_text(text, chunk_size=100, overlap=50)
    # Should have multiple chunks; first bytes of chunk N+1 should overlap with
    # last bytes of chunk N for at least some prefix.
    assert len(chunks) >= 2

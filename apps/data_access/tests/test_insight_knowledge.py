"""Unit tests for the knowledge insight function.

Mocks ``search_chunks`` so the test does not require pgvector/Postgres.
"""

from __future__ import annotations

from unittest.mock import patch

from apps.data_access.knowledge.search import SearchHit
from apps.data_access.insight_functions.knowledge import (
    KnowledgeAnswerContext,
    search_company_knowledge,
)


def _hit(idx: int = 0) -> SearchHit:
    return SearchHit(
        chunk_id=f"chunk-{idx}",
        document_id=idx + 1,
        chunk_index=idx,
        text=f"sample text {idx}",
        similarity=0.9 - 0.05 * idx,
        metadata={"title": f"Doc {idx}", "web_view_link": f"https://drive/{idx}"},
    )


def test_returns_empty_context_when_no_hits() -> None:
    with patch(
        "apps.data_access.insight_functions.knowledge.search_chunks", return_value=[]
    ):
        ctx = search_company_knowledge("dotaz")
    assert isinstance(ctx, KnowledgeAnswerContext)
    assert ctx.query == "dotaz"
    assert ctx.hits == []
    assert ctx.prompt_context == ""


def test_propagates_hits_and_renders_prompt_context() -> None:
    hits = [_hit(0), _hit(1)]
    with patch(
        "apps.data_access.insight_functions.knowledge.search_chunks", return_value=hits
    ):
        ctx = search_company_knowledge("strategie", top_k=2)
    assert len(ctx.hits) == 2
    assert ctx.hits[0]["chunk_id"] == "chunk-0"
    assert "[1] Doc 0" in ctx.prompt_context
    assert "[2] Doc 1" in ctx.prompt_context


def test_passes_filters_to_search() -> None:
    with patch(
        "apps.data_access.insight_functions.knowledge.search_chunks", return_value=[]
    ) as mock:
        search_company_knowledge("q", top_k=5, source="drive", owner_email="x@y.z")
    mock.assert_called_once_with(
        "q", top_k=5, source="drive", owner_email="x@y.z"
    )

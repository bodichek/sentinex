"""Tests for the KnowledgeSpecialist — RAG flow with mocked search + LLM."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.agents.base import AgentContext
from apps.agents.specialists.knowledge import KnowledgeSpecialist
from apps.data_access.insight_functions.knowledge import KnowledgeAnswerContext


@pytest.fixture
def fake_llm_response():  # type: ignore[no-untyped-def]
    from apps.agents.llm_gateway import LLMResponse

    return LLMResponse(
        content="Stručná odpověď s citací [1].",
        model="claude-sonnet-4",
        input_tokens=100,
        output_tokens=20,
        cost_usd=0.001,
        cost_czk=0.024,
        cache_hit=False,
        latency_ms=500,
    )


def test_specialist_returns_no_context_when_index_empty(fake_llm_response) -> None:  # type: ignore[no-untyped-def]
    empty_ctx = KnowledgeAnswerContext(query="x", hits=[], prompt_context="")
    with patch(
        "apps.data_access.insight_functions.knowledge.search_company_knowledge",
        return_value=empty_ctx,
    ):
        spec = KnowledgeSpecialist()
        resp = spec.analyze(AgentContext(query="cokoliv"))
    assert resp.confidence == 0.2
    assert "nenašel" in resp.content.lower() or "není naplněn" in resp.content.lower()


def test_specialist_calls_llm_with_retrieved_context(fake_llm_response) -> None:  # type: ignore[no-untyped-def]
    hits_ctx = KnowledgeAnswerContext(
        query="X",
        hits=[
            {
                "chunk_id": "abc",
                "document_id": 1,
                "chunk_index": 0,
                "text": "Cenotvorba 2026 vychází z marže 30 %",
                "similarity": 0.91,
                "metadata": {"title": "Strategy.gdoc", "web_view_link": "https://drive/x"},
            }
        ],
        prompt_context="[1] Strategy.gdoc — https://drive/x\nCenotvorba 2026 ...",
    )
    with patch(
        "apps.agents.specialists.knowledge.search_company_knowledge",
        return_value=hits_ctx,
    ), patch(
        "apps.agents.specialists.knowledge.complete", return_value=fake_llm_response
    ) as complete_mock, patch(
        "apps.agents.specialists.knowledge.load_prompt", return_value="SYSTEM"
    ):
        spec = KnowledgeSpecialist()
        resp = spec.analyze(AgentContext(query="cenotvorba 2026"))

    complete_mock.assert_called_once()
    user_prompt = complete_mock.call_args.args[0]
    assert "cenotvorba 2026" in user_prompt
    assert "[1] Strategy.gdoc" in user_prompt
    assert resp.structured_data["citation_count"] == 1
    assert resp.content.startswith("Stručná odpověď")

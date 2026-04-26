"""PeopleSpecialist + orchestrator-registration tests."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.agents.base import AgentContext
from apps.agents.llm_gateway import LLMResponse
from apps.agents.specialists import REGISTRY, PeopleSpecialist
from apps.agents.specialists.people import PeopleAnalysis


def _mk_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="claude-haiku-4-5-20251001",
        input_tokens=10,
        output_tokens=5,
        cost_czk=Decimal("0"),
        cached=False,
        latency_ms=0,
    )


@pytest.mark.django_db
class TestPeopleSpecialist:
    def test_people_specialist_analyze(self) -> None:
        payload = {
            "capacity_score": 0.62,
            "hiring_health": "at_risk",
            "risks": ["Senior engineer overload", "No backup for finance lead"],
            "recommendations": ["Hire backup for finance lead within 60 days"],
            "confidence": 0.7,
        }
        ctx = AgentContext(query="Jak na tom je tým?")
        with patch("apps.agents.base.complete", return_value=_mk_response(json.dumps(payload))):
            resp = PeopleSpecialist().analyze(ctx)

        assert resp.name == "people"
        analysis = PeopleAnalysis.model_validate(resp.structured_data)
        assert analysis.capacity_score == pytest.approx(0.62)
        assert analysis.hiring_health == "at_risk"
        assert len(analysis.risks) == 2
        assert resp.confidence == pytest.approx(0.7)


def test_orchestrator_includes_people() -> None:
    assert "people" in REGISTRY
    assert REGISTRY["people"] is PeopleSpecialist

"""OpsSpecialist + orchestrator-registration tests."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.agents.base import AgentContext
from apps.agents.llm_gateway import LLMResponse
from apps.agents.specialists import REGISTRY, OpsSpecialist
from apps.agents.specialists.ops import OpsAnalysis


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
class TestOpsSpecialist:
    def test_ops_specialist_analyze(self) -> None:
        payload = {
            "reliability_score": 0.78,
            "deployment_health": "degraded",
            "incidents": ["3× P2 in last 14d on payments service"],
            "cost_trend": "rising",
            "recommendations": ["Add canary on payments deploy pipeline"],
            "confidence": 0.7,
        }
        ctx = AgentContext(query="Jak na tom je infra?")
        with patch("apps.agents.base.complete", return_value=_mk_response(json.dumps(payload))):
            resp = OpsSpecialist().analyze(ctx)

        assert resp.name == "ops"
        analysis = OpsAnalysis.model_validate(resp.structured_data)
        assert analysis.reliability_score == pytest.approx(0.78)
        assert analysis.deployment_health == "degraded"
        assert analysis.cost_trend == "rising"
        assert len(analysis.incidents) == 1
        assert resp.confidence == pytest.approx(0.7)


def test_orchestrator_includes_ops() -> None:
    assert "ops" in REGISTRY
    assert REGISTRY["ops"] is OpsSpecialist

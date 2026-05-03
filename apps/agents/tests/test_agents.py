"""Orchestrator + specialist tests with mocked LLM Gateway."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from django_tenants.utils import schema_context

from apps.agents import context_builder, orchestrator
from apps.agents.base import AgentContext
from apps.agents.llm_gateway import LLMResponse, ToolUseResponse
from apps.agents.orchestrator import Orchestrator
from apps.agents.specialists import FinanceSpecialist, StrategicSpecialist


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


def _mk_tool_response(content: str) -> ToolUseResponse:
    return ToolUseResponse(
        content=content,
        model="claude-haiku-4-5-20251001",
        input_tokens=10,
        output_tokens=5,
        cost_czk=Decimal("0"),
        latency_ms=0,
        iterations=1,
        tool_calls=[],
    )


@pytest.mark.django_db
class TestSpecialist:
    def test_strategic_calls_gateway(self) -> None:
        ctx = AgentContext(query="Jak na tom jsme strategicky?")
        # Strategic is a tool-using specialist now → patch complete_with_tools.
        with patch(
            "apps.agents.base.complete_with_tools",
            return_value=_mk_tool_response("OK-strategic"),
        ) as mock:
            resp = StrategicSpecialist().analyze(ctx)
        assert resp.name == "strategic"
        assert resp.content == "OK-strategic"
        assert mock.call_count == 1

    def test_finance_calls_gateway(self) -> None:
        ctx = AgentContext(query="Jak je na tom cashflow?")
        with patch(
            "apps.agents.base.complete_with_tools",
            return_value=_mk_tool_response("OK-finance"),
        ):
            resp = FinanceSpecialist().analyze(ctx)
        assert resp.name == "finance"
        assert resp.content == "OK-finance"


@pytest.mark.django_db
class TestOrchestrator:
    def test_classify_intent_parses_json(self) -> None:
        raw = (
            '{"intent":"cashflow","summary":"runway question",'
            '"required_specialists":["finance"],"reasoning":"money"}'
        )
        with patch.object(orchestrator, "complete", return_value=_mk_response(raw)):
            intent = Orchestrator().classify_intent("runway?")
        assert intent.intent == "cashflow"
        assert intent.required_specialists == ["finance"]

    def test_classify_intent_drops_unknown_specialists(self) -> None:
        raw = '{"intent":"x","summary":"","required_specialists":["mystery","finance"]}'
        with patch.object(orchestrator, "complete", return_value=_mk_response(raw)):
            intent = Orchestrator().classify_intent("q")
        assert intent.required_specialists == ["finance"]

    def test_classify_intent_fails_loudly_on_bad_json(self) -> None:
        with (
            patch.object(orchestrator, "complete", return_value=_mk_response("not json")),
            pytest.raises(ValueError, match="non-JSON"),
        ):
            Orchestrator().classify_intent("q")

    def test_end_to_end_flow(self) -> None:
        intent_json = (
            '{"intent":"health","summary":"business health",'
            '"required_specialists":["strategic","finance"]}'
        )
        # Orchestrator uses complete() for classify_intent + compose;
        # specialists now use complete_with_tools().
        complete_responses = iter(
            [_mk_response(intent_json), _mk_response("combined summary")]
        )
        tool_responses = iter(
            [_mk_tool_response("strategic output"), _mk_tool_response("finance output")]
        )

        def fake_complete(*args: object, **kwargs: object) -> LLMResponse:
            return next(complete_responses)

        def fake_complete_with_tools(*args: object, **kwargs: object) -> ToolUseResponse:
            return next(tool_responses)

        with schema_context("test_tenant"):
            ctx = context_builder.build("Jak se nám daří?", insights=())
        with (
            patch.object(orchestrator, "complete", side_effect=fake_complete),
            patch("apps.agents.base.complete_with_tools", side_effect=fake_complete_with_tools),
        ):
            result = Orchestrator().handle("Jak se nám daří?", ctx)

        names = [s.name for s in result.specialist_responses]
        assert names == ["strategic", "finance"]
        assert result.final == "combined summary"

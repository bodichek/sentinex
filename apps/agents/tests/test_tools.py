"""Unit tests for the agent tool registry + tool-using specialist path."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.agents import tools as tool_registry
from apps.agents.base import AgentContext
from apps.agents.llm_gateway import ToolCall, ToolUseResponse
from apps.agents.specialists.finance import FinanceSpecialist
from apps.agents.specialists.strategic import StrategicSpecialist


def test_anthropic_tool_specs_match_registry() -> None:
    names = ("get_cashflow_snapshot", "get_marketing_funnel")
    specs = tool_registry.anthropic_tool_specs(names)
    assert [s["name"] for s in specs] == list(names)
    assert all("description" in s and "input_schema" in s for s in specs)


def test_anthropic_tool_specs_rejects_unknown() -> None:
    with pytest.raises(KeyError):
        tool_registry.anthropic_tool_specs(("bogus_tool",))


def test_invoke_tool_unknown_returns_json_error() -> None:
    payload = json.loads(tool_registry.invoke_tool("bogus_tool"))
    assert payload == {"ok": False, "error": "unknown_tool", "tool": "bogus_tool"}


def test_wrap_serialises_dataclass_results() -> None:
    from dataclasses import dataclass

    from apps.agents.tools import _serialize, _wrap

    @dataclass
    class Foo:
        x: int

    fn = _wrap(lambda: Foo(x=7))
    assert fn() == {"ok": True, "data": {"x": 7}}
    assert _serialize([Foo(x=1), {"a": Foo(x=2)}]) == [{"x": 1}, {"a": {"x": 2}}]


def test_wrap_handles_insufficient_data() -> None:
    from apps.agents.tools import _wrap
    from apps.data_access.insight_functions.exceptions import InsufficientData

    fn = _wrap(lambda: (_ for _ in ()).throw(InsufficientData("no snapshot")))
    assert fn() == {
        "ok": False,
        "error": "insufficient_data",
        "reason": "no snapshot",
    }


def test_strategic_specialist_advertises_tool_set() -> None:
    spec = StrategicSpecialist()
    assert "get_weekly_metrics" in spec.tool_names
    assert "search_company_knowledge" in spec.tool_names


def test_finance_specialist_advertises_tool_set() -> None:
    spec = FinanceSpecialist()
    assert spec.tool_names == (
        "get_cashflow_snapshot",
        "get_marketing_funnel",
        "get_pipeline_velocity",
    )


def test_tool_using_specialist_records_tool_calls_in_structured_data() -> None:
    fake_response = ToolUseResponse(
        content="Cash je v pohodě, runway 14 měsíců.",
        model="claude-sonnet-4",
        input_tokens=120,
        output_tokens=40,
        cost_czk=__import__("decimal").Decimal("0.5"),
        latency_ms=900,
        iterations=2,
        tool_calls=[
            ToolCall(
                name="get_cashflow_snapshot",
                arguments={},
                result='{"ok": true, "data": {"cash_on_hand": 1000000}}',
            )
        ],
    )
    with patch(
        "apps.agents.base.complete_with_tools", return_value=fake_response
    ) as mock_complete, patch(
        "apps.agents.base.load_prompt", return_value="SYSTEM"
    ):
        result = FinanceSpecialist().analyze(AgentContext(query="Jak jsme na tom finančně?"))

    mock_complete.assert_called_once()
    call_kwargs = mock_complete.call_args.kwargs
    assert call_kwargs["system"] == "SYSTEM"
    assert {t["name"] for t in call_kwargs["tools"]} == {
        "get_cashflow_snapshot",
        "get_marketing_funnel",
        "get_pipeline_velocity",
    }
    assert result.content.startswith("Cash je v pohodě")
    assert result.structured_data["iterations"] == 2
    assert result.structured_data["tool_calls"][0]["name"] == "get_cashflow_snapshot"

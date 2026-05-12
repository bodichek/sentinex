"""Tests for the Research Agent LangGraph workflow."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from apps.agents.graphs.research_agent import (
    ResearchAgentGraph,
    generate_response_node,
    retrieve_context_node,
    update_memory_node,
)


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


def test_retrieve_context_initialises_memory_key() -> None:
    state: dict[str, Any] = {}
    out = _run(retrieve_context_node(state))  # type: ignore[arg-type]
    assert out["memory_context"] == []


def test_update_memory_passes_state_through() -> None:
    state: dict[str, Any] = {"messages": [HumanMessage(content="hi")]}
    out = _run(update_memory_node(state))  # type: ignore[arg-type]
    assert out is state


def test_generate_response_appends_ai_message() -> None:
    fake_response = AIMessage(content="hello world")
    with patch(
        "apps.agents.graphs.research_agent.ChatAnthropic"
    ) as mock_chat:
        instance = mock_chat.return_value
        instance.ainvoke = AsyncMock(return_value=fake_response)

        state: dict[str, Any] = {"messages": [HumanMessage(content="hi")]}
        out = _run(generate_response_node(state))  # type: ignore[arg-type]

    assert isinstance(out["messages"][-1], AIMessage)
    assert out["messages"][-1].content == "hello world"
    assert out["confidence"] == 1.0


def test_research_graph_builds() -> None:
    graph = ResearchAgentGraph(tenant_id="t1").build()
    compiled = graph.compile()
    assert compiled is not None

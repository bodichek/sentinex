"""Research Agent — first concrete LangGraph workflow.

Nodes:
    * :func:`retrieve_context_node` — fetch relevant context (pgvector + memory stub)
    * :func:`generate_response_node` — call Claude via ChatAnthropic
    * :func:`update_memory_node` — persist new facts (stub; replaced by prompt 14)

The memory nodes are intentionally lightweight stubs in this prompt; prompt 14
swaps them for Graphiti-backed implementations in :mod:`apps.memory`.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from apps.agents.graphs.base import TenantStateGraph
from apps.agents.graphs.state import AgentState

logger = logging.getLogger("sentinex.agents.research")

CONFIDENCE_THRESHOLD = 0.4


async def retrieve_context_node(state: AgentState) -> AgentState:
    """Fetch relevant context for the latest user message via Graphiti."""
    from apps.agents.graphs.nodes.memory_nodes import read_memory_node

    return await read_memory_node(state)


async def generate_response_node(state: AgentState) -> AgentState:
    """Call Claude with the current message history and any retrieved context."""
    model = ChatAnthropic(
        model=getattr(settings, "ANTHROPIC_RESEARCH_MODEL", "claude-haiku-4-5"),
        api_key=getattr(settings, "ANTHROPIC_API_KEY", None),
        temperature=0.2,
    )

    messages = list(state.get("messages") or [])
    if not messages:
        messages = [HumanMessage(content="(no input)")]

    memory = state.get("memory_context") or []
    if memory:
        memory_blob = "\n".join(str(m) for m in memory[:10])
        messages = [
            HumanMessage(content=f"Relevant memory context:\n{memory_blob}"),
            *messages,
        ]

    response: Any = await model.ainvoke(messages)
    content = getattr(response, "content", str(response))

    state["messages"] = [*state.get("messages", []), AIMessage(content=content)]
    state["confidence"] = 1.0
    return state


async def update_memory_node(state: AgentState) -> AgentState:
    """Persist new facts learned during the run via Graphiti."""
    from apps.agents.graphs.nodes.memory_nodes import write_memory_node

    return await write_memory_node(state)


def _route_after_generate(state: AgentState) -> str:
    if state.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        return "retrieve_context"
    return "update_memory"


class ResearchAgentGraph(TenantStateGraph):
    """Compiled LangGraph for the Research Agent."""

    agent_id = "research"

    def build(self) -> StateGraph:
        graph: StateGraph = StateGraph(AgentState)
        graph.add_node("retrieve_context", retrieve_context_node)
        graph.add_node("generate_response", generate_response_node)
        graph.add_node("update_memory", update_memory_node)

        graph.set_entry_point("retrieve_context")
        graph.add_edge("retrieve_context", "generate_response")
        graph.add_conditional_edges(
            "generate_response",
            _route_after_generate,
            {"retrieve_context": "retrieve_context", "update_memory": "update_memory"},
        )
        graph.add_edge("update_memory", END)
        return graph

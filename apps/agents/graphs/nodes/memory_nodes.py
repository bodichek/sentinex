"""Graphiti-backed read/write nodes used by LangGraph agents.

These replace the stubs in ``apps.agents.graphs.research_agent`` once a tenant
has Neo4j configured. They are wired into the Research Agent via
:func:`apps.agents.graphs.research_agent.ResearchAgentGraph`.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.agents.graphs.state import AgentState
from apps.memory.graphiti_client import TenantGraphitiClient

logger = logging.getLogger("sentinex.agents.memory")

_client = TenantGraphitiClient()


def _last_user_text(state: AgentState) -> str:
    msgs = state.get("messages") or []
    if not msgs:
        return ""
    return getattr(msgs[-1], "content", "") or ""


async def read_memory_node(state: AgentState) -> AgentState:
    """Fetch the most relevant facts for the current user message."""
    tenant_id = state.get("tenant_id")
    if not tenant_id:
        state.setdefault("memory_context", [])
        return state

    query = _last_user_text(state)
    if not query:
        state.setdefault("memory_context", [])
        return state

    try:
        edges: list[Any] = await _client.search(tenant_id, query, num_results=10)
    except Exception:  # noqa: BLE001
        logger.exception("graphiti search failed; falling back to empty context")
        state["memory_context"] = []
        return state

    state["memory_context"] = [
        {
            "uuid": getattr(e, "uuid", None),
            "fact": getattr(e, "fact", None),
            "valid_at": str(getattr(e, "valid_at", "") or ""),
        }
        for e in edges
    ]
    return state


async def write_memory_node(state: AgentState) -> AgentState:
    """Persist the most recent assistant turn into the tenant's graph."""
    tenant_id = state.get("tenant_id")
    msgs = state.get("messages") or []
    if not tenant_id or not msgs:
        return state

    last = msgs[-1]
    content = getattr(last, "content", "") or ""
    if not content:
        return state

    try:
        await _client.add_episode(
            tenant_id,
            content,
            name=f"agent:{state.get('agent_id', 'unknown')}",
            source_description="agent_turn",
            metadata=state.get("metadata") or {},
        )
    except Exception:  # noqa: BLE001
        logger.exception("graphiti add_episode failed; continuing without persistence")

    return state

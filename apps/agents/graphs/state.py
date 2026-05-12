"""Shared state schemas for LangGraph agent workflows."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Tenant-scoped state passed between graph nodes."""

    tenant_id: str
    agent_id: str
    session_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    memory_context: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    metadata: dict[str, Any]
    confidence: float

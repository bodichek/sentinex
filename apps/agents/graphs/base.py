"""TenantStateGraph base class for LangGraph agent workflows."""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph

from apps.agents.checkpointers import checkpoint_config
from apps.agents.graphs.state import AgentState


class TenantStateGraph:
    """Wrap a ``StateGraph`` with tenant context, Langfuse callbacks and checkpointing.

    Subclasses implement :meth:`build` returning a compiled graph.
    """

    agent_id: str = "base"

    def __init__(self, tenant_id: str, *, ttl_seconds: int = 24 * 60 * 60) -> None:
        self.tenant_id = tenant_id
        self.ttl_seconds = ttl_seconds
        self._graph: Any | None = None

    def build(self) -> StateGraph:
        """Build (uncompiled) StateGraph. Subclasses must override."""
        raise NotImplementedError

    async def compiled(self, checkpointer: Any | None = None) -> Any:
        if self._graph is None:
            graph = self.build()
            self._graph = graph.compile(checkpointer=checkpointer)
        return self._graph

    def _langfuse_handler(self, agent_type: str) -> Any | None:
        from apps.observability.langfuse_client import get_client

        return get_client().get_callback_handler(
            tenant_id=self.tenant_id,
            agent_type=agent_type,
        )

    def runnable_config(
        self,
        session_id: str,
        *,
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        cfg = checkpoint_config(
            self.tenant_id,
            self.agent_id,
            session_id,
            ttl_seconds=self.ttl_seconds,
        )
        handler = self._langfuse_handler(agent_type or self.agent_id)
        if handler is not None:
            cfg["callbacks"] = [handler]
        return cfg

    async def ainvoke(
        self,
        state: AgentState,
        session_id: str,
        *,
        checkpointer: Any | None = None,
    ) -> AgentState:
        graph = await self.compiled(checkpointer=checkpointer)
        cfg = self.runnable_config(session_id)
        result = await graph.ainvoke(state, config=cfg)
        return result  # type: ignore[no-any-return]

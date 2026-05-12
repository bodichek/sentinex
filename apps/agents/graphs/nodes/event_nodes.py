"""LangGraph nodes that publish lifecycle events to Kafka."""

from __future__ import annotations

import logging
from uuid import uuid4

from apps.agents.graphs.state import AgentState
from apps.events.kafka_client import SentinexKafkaProducer

logger = logging.getLogger("sentinex.agents.events")

_producer = SentinexKafkaProducer()


async def _publish(state: AgentState, event_type: str) -> None:
    tenant_id = state.get("tenant_id")
    if not tenant_id:
        return
    run_id = (state.get("metadata") or {}).get("run_id") or str(uuid4())
    try:
        await _producer.publish(
            tenant_id=tenant_id,
            category="agent",
            event_type=event_type,
            payload={"messages_count": len(state.get("messages") or [])},
            extra={
                "agent_type": state.get("agent_id", "unknown"),
                "run_id": run_id,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to publish %s", event_type)


async def publish_run_started_node(state: AgentState) -> AgentState:
    await _publish(state, "run.started")
    return state


async def publish_run_completed_node(state: AgentState) -> AgentState:
    await _publish(state, "run.completed")
    return state


async def publish_run_failed_node(state: AgentState) -> AgentState:
    await _publish(state, "run.failed")
    return state

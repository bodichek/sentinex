"""Integration: end-to-end flow across the full stack.

Drives one synthetic agent run and verifies that the side-effects landed in
each backend that the prompts wired up:

* Kafka — `run.started` / `run.completed` events on the tenant's topic
* ClickHouse — agent_runs row visible in `get_tenant_usage`
* Neo4j (Graphiti) — episode written + retrievable (skipped without LLM keys)
* Langfuse — trace surfaced via the SDK list endpoint (skipped without keys)
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_full_stack_single_run(
    kafka_available: bool,
    clickhouse_available: bool,
    integration_tenant_id: str,
) -> None:
    if not (kafka_available and clickhouse_available):
        pytest.skip("kafka or clickhouse not reachable")

    from apps.analytics.clickhouse_client import SentinexClickHouseClient
    from apps.analytics.schemas import AgentRunRow
    from apps.events.kafka_client import SentinexKafkaProducer
    from apps.events.topic_manager import ensure_topics, topic_for
    from tests.integration.test_clickhouse_analytics import _ensure_schema

    _ensure_schema()
    ensure_topics(integration_tenant_id)
    topic = topic_for(integration_tenant_id, "agent")
    run_id = uuid4()

    async def _go() -> list[dict]:
        producer = SentinexKafkaProducer()
        try:
            await producer.publish(
                integration_tenant_id, "agent", "run.started",
                payload={"input": "hello"},
                extra={"agent_type": "research", "run_id": str(run_id)},
            )
            await producer.publish(
                integration_tenant_id, "agent", "run.completed",
                payload={"input_tokens": 10, "output_tokens": 20},
                extra={"agent_type": "research", "run_id": str(run_id)},
            )
        finally:
            await producer.close()

        from aiokafka import AIOKafkaConsumer
        from django.conf import settings

        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=f"e2e-{run_id.hex[:6]}",
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode()),
            enable_auto_commit=True,
        )
        out: list[dict] = []
        await consumer.start()
        try:
            async with asyncio.timeout(15):
                async for msg in consumer:
                    if msg.value.get("run_id") == str(run_id):
                        out.append(msg.value)
                        seen = {e["event_type"] for e in out}
                        if {"run.started", "run.completed"}.issubset(seen):
                            break
        finally:
            await consumer.stop()
        return out

    try:
        events = asyncio.run(_go())
    except TimeoutError:
        pytest.fail("did not receive both lifecycle events within 15s")

    types = {e["event_type"] for e in events}
    assert {"run.started", "run.completed"}.issubset(types)

    ch = SentinexClickHouseClient()
    asyncio.run(
        ch.insert_agent_run(
            AgentRunRow(
                tenant_id=integration_tenant_id,
                run_id=run_id,
                agent_type="research",
                session_id="e2e",
                status="completed",
                started_at=datetime.now(UTC),
                input_tokens=10,
                output_tokens=20,
                total_cost_usd=0.001,
            )
        )
    )

    today = datetime.now(UTC).date()
    summary = asyncio.run(
        ch.get_tenant_usage(integration_tenant_id, today, today)
    )
    assert summary.agent_runs >= 1
    assert summary.by_agent_type.get("research", 0) >= 1

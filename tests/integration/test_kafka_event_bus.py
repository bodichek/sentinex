"""Integration: Kafka topic provisioning + producer → consumer round-trip."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest

pytestmark = [pytest.mark.integration]


def test_topic_create_then_list(kafka_available: bool, integration_tenant_id: str) -> None:
    if not kafka_available:
        pytest.skip("kafka not reachable")
    from apps.events.topic_manager import ensure_topics, list_topics, topics_for_tenant

    desired = ensure_topics(integration_tenant_id)
    assert sorted(desired) == sorted(topics_for_tenant(integration_tenant_id))
    all_topics = list_topics()
    for t in desired:
        assert t in all_topics


def test_producer_consumer_roundtrip(kafka_available: bool, integration_tenant_id: str) -> None:
    if not kafka_available:
        pytest.skip("kafka not reachable")
    from apps.events.kafka_client import SentinexKafkaConsumer, SentinexKafkaProducer
    from apps.events.topic_manager import ensure_topics, topic_for

    ensure_topics(integration_tenant_id)
    topic = topic_for(integration_tenant_id, "agent")

    received: list[dict[str, Any]] = []

    async def _go() -> None:
        producer = SentinexKafkaProducer()
        try:
            run_id = str(uuid.uuid4())
            await producer.publish(
                tenant_id=integration_tenant_id,
                category="agent",
                event_type="run.started",
                payload={"input": "hello"},
                extra={"agent_type": "research", "run_id": run_id},
            )
        finally:
            await producer.close()

        from aiokafka import AIOKafkaConsumer

        from django.conf import settings

        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=f"itest-{uuid.uuid4().hex[:6]}",
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode()),
            enable_auto_commit=True,
        )
        await consumer.start()
        try:
            async with asyncio.timeout(10):
                async for msg in consumer:
                    received.append(msg.value)
                    if msg.value.get("event_type") == "run.started":
                        break
        finally:
            await consumer.stop()

    try:
        asyncio.run(_go())
    except TimeoutError:
        pytest.fail("did not receive published event within 10s")

    assert received
    assert any(e.get("tenant_id") == integration_tenant_id for e in received)

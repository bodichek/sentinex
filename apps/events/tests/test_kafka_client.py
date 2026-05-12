"""Tests for the Kafka producer/consumer wrappers (mocked broker)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.events.kafka_client import SentinexKafkaProducer


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


def test_producer_publishes_to_expected_topic() -> None:
    fake = MagicMock()
    fake.send_and_wait = AsyncMock(return_value=None)
    fake.start = AsyncMock(return_value=None)
    producer = SentinexKafkaProducer(producer=fake)

    topic = _run(
        producer.publish(
            tenant_id="acme",
            category="agent",
            event_type="run.started",
            payload={"x": 1},
            extra={"agent_type": "research", "run_id": "00000000-0000-0000-0000-000000000001"},
        )
    )

    assert topic == "acme.events.agent"
    args, kwargs = fake.send_and_wait.await_args
    assert args[0] == "acme.events.agent"


def test_producer_rejects_unknown_category() -> None:
    fake = MagicMock()
    producer = SentinexKafkaProducer(producer=fake)
    with pytest.raises(ValueError):
        _run(
            producer.publish(
                tenant_id="acme",
                category="bogus",
                event_type="x",
                payload={},
            )
        )


def test_producer_isolates_tenants_in_topic() -> None:
    fake = MagicMock()
    fake.send_and_wait = AsyncMock(return_value=None)
    fake.start = AsyncMock(return_value=None)
    producer = SentinexKafkaProducer(producer=fake)

    _run(
        producer.publish(
            "tenant-a", "system", "tenant.created", {}, extra={}
        )
    )
    _run(
        producer.publish(
            "tenant-b", "system", "tenant.created", {}, extra={}
        )
    )
    topics = [c.args[0] for c in fake.send_and_wait.await_args_list]
    assert topics[0] != topics[1]

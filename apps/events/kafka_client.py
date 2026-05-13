"""Async Kafka producer and consumer wrappers."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from django.conf import settings

from apps.events.schemas import (
    AgentRunEvent,
    BaseEvent,
    EventCategory,
    SystemEvent,
    UserEvent,
)
from apps.events.topic_manager import topic_for

if TYPE_CHECKING:  # pragma: no cover
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = logging.getLogger("sentinex.events")

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]

_EVENT_CLASSES: dict[str, type[BaseEvent]] = {
    EventCategory.AGENT.value: AgentRunEvent,
    EventCategory.SYSTEM.value: SystemEvent,
    EventCategory.USER.value: UserEvent,
}


def _bootstrap() -> str:
    return getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def _serialize(value: Any) -> bytes:
    if hasattr(value, "model_dump_json"):
        encoded: bytes = value.model_dump_json().encode("utf-8")
        return encoded
    return json.dumps(value, default=str).encode("utf-8")


class SentinexKafkaProducer:
    """Async wrapper around :class:`aiokafka.AIOKafkaProducer`."""

    def __init__(self, producer: AIOKafkaProducer | None = None) -> None:
        self._producer = producer
        self._owns_producer = producer is None

    async def _ensure(self) -> AIOKafkaProducer:
        if self._producer is None:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=_bootstrap(),
                value_serializer=_serialize,
                client_id="sentinex-producer",
            )
            await self._producer.start()
        return self._producer

    async def publish(
        self,
        tenant_id: str,
        category: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Publish an event. Returns the topic name."""
        cls = _EVENT_CLASSES.get(category)
        if cls is None:
            raise ValueError(f"Unknown category: {category}")
        body = {"tenant_id": tenant_id, "event_type": event_type, "payload": payload}
        if extra:
            body.update(extra)
        event = cls.model_validate(body)
        topic = topic_for(tenant_id, category)
        producer = await self._ensure()
        await producer.send_and_wait(topic, event)
        logger.debug("kafka publish %s %s", topic, event_type)
        return topic

    async def close(self) -> None:
        if self._producer is not None and self._owns_producer:
            await self._producer.stop()
            self._producer = None


class SentinexKafkaConsumer:
    """Async wrapper around :class:`aiokafka.AIOKafkaConsumer`."""

    def __init__(self, consumer: AIOKafkaConsumer | None = None) -> None:
        self._consumer = consumer
        self._stop = False

    async def subscribe(
        self,
        tenant_id: str,
        categories: list[str],
        handler: EventHandler,
        *,
        group_id: str = "sentinex-consumer",
    ) -> None:
        """Subscribe to a tenant's topics and dispatch every record to ``handler``."""
        from aiokafka import AIOKafkaConsumer

        topics = [topic_for(tenant_id, c) for c in categories]
        if self._consumer is None:
            self._consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=_bootstrap(),
                group_id=group_id,
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await self._consumer.start()
        try:
            async for msg in self._consumer:
                if self._stop:
                    break
                try:
                    await handler(msg.value)
                except Exception:
                    logger.exception("handler failed; dropping into DLQ topic")
                    await self._send_to_dlq(msg.topic, msg.value)
        finally:
            await self._consumer.stop()
            self._consumer = None

    async def _send_to_dlq(self, source_topic: str, value: Any) -> None:
        producer = SentinexKafkaProducer()
        try:
            inner = await producer._ensure()
            await inner.send_and_wait(f"{source_topic}.dlq", value)
        finally:
            await producer.close()

    def stop(self) -> None:
        self._stop = True

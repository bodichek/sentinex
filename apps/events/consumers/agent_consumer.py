"""Long-running consumer for agent-category events.

Routes to small handlers based on ``event_type``. Failed records are sent to
``<topic>.dlq`` by the consumer wrapper.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger("sentinex.events.agent")

HANDLERS: dict[str, Any] = {}


def handler(event_type: str):  # type: ignore[no-untyped-def]
    def deco(fn):  # type: ignore[no-untyped-def]
        HANDLERS[event_type] = fn
        return fn

    return deco


@handler("run.started")
async def on_run_started(event: dict[str, Any]) -> None:
    logger.info("run started: tenant=%s run=%s", event.get("tenant_id"), event.get("run_id"))


@handler("run.completed")
async def on_run_completed(event: dict[str, Any]) -> None:
    logger.info(
        "run completed: tenant=%s run=%s",
        event.get("tenant_id"),
        event.get("run_id"),
    )


@handler("run.failed")
async def on_run_failed(event: dict[str, Any]) -> None:
    logger.warning(
        "run failed: tenant=%s run=%s",
        event.get("tenant_id"),
        event.get("run_id"),
    )


async def dispatch(event: dict[str, Any]) -> None:
    fn = HANDLERS.get(event.get("event_type", ""))
    if fn is None:
        logger.debug("no handler for %s", event.get("event_type"))
        return
    await fn(event)


@shared_task(name="events.consume_agent_events")  # type: ignore[untyped-decorator]
def consume_agent_events(tenant_id: str = "all", group_id: str = "sentinex-agent") -> None:
    """Celery entrypoint — drains Kafka into :func:`dispatch` until stopped."""
    import asyncio

    from apps.events.kafka_client import SentinexKafkaConsumer

    async def _run() -> None:
        consumer = SentinexKafkaConsumer()
        await consumer.subscribe(tenant_id, ["agent"], dispatch, group_id=group_id)

    asyncio.run(_run())

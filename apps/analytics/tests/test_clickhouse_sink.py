"""Tests for the Kafka → ClickHouse sink consumer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from apps.analytics.clickhouse_client import SentinexClickHouseClient
from apps.analytics.consumers.clickhouse_sink import BATCH_SIZE, ClickHouseSink


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


def _agent_event(**over: Any) -> dict[str, Any]:
    base = {
        "event_id": str(uuid4()),
        "tenant_id": "t1",
        "agent_type": "research",
        "run_id": str(uuid4()),
        "event_type": "run.started",
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {"session_id": "s1"},
    }
    base.update(over)
    return base


def test_sink_buffers_below_batch_size() -> None:
    ch = SentinexClickHouseClient(client=MagicMock())
    ch.insert_agent_run = AsyncMock()  # type: ignore[method-assign]
    sink = ClickHouseSink(client=ch)
    _run(sink.handle(_agent_event()))
    assert ch.insert_agent_run.await_count == 0
    assert len(sink._agent_buffer) == 1


def test_sink_deduplicates_by_event_id() -> None:
    ch = SentinexClickHouseClient(client=MagicMock())
    ch.insert_agent_run = AsyncMock()  # type: ignore[method-assign]
    sink = ClickHouseSink(client=ch)
    e = _agent_event()
    _run(sink.handle(e))
    _run(sink.handle(e))
    assert len(sink._agent_buffer) == 1


def test_sink_flushes_on_batch_size() -> None:
    ch = SentinexClickHouseClient(client=MagicMock())
    ch.insert_agent_run = AsyncMock()  # type: ignore[method-assign]
    sink = ClickHouseSink(client=ch)
    for _ in range(BATCH_SIZE):
        _run(sink.handle(_agent_event()))
    assert ch.insert_agent_run.await_count == BATCH_SIZE
    assert sink._agent_buffer == []


def test_sink_routes_system_events_to_separate_buffer() -> None:
    ch = SentinexClickHouseClient(client=MagicMock())
    ch.insert_system_event = AsyncMock()  # type: ignore[method-assign]
    ch.insert_agent_run = AsyncMock()  # type: ignore[method-assign]
    sink = ClickHouseSink(client=ch)
    _run(
        sink.handle(
            {
                "event_id": str(uuid4()),
                "tenant_id": "t1",
                "event_type": "tenant.created",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {},
            }
        )
    )
    assert len(sink._system_buffer) == 1
    assert sink._agent_buffer == []

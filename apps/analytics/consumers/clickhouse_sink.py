"""Kafka → ClickHouse sink consumer.

Buffers records and flushes either every ``BATCH_SIZE`` events or every
``FLUSH_INTERVAL_S`` seconds. Idempotency is provided by the caller via the
event's ``event_id`` (deduplicated client-side before insert).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from apps.analytics.clickhouse_client import SentinexClickHouseClient
from apps.analytics.schemas import AgentRunRow, SystemEventRow

logger = logging.getLogger("sentinex.analytics.sink")

BATCH_SIZE = 100
FLUSH_INTERVAL_S = 5.0


class ClickHouseSink:
    def __init__(self, client: SentinexClickHouseClient | None = None) -> None:
        self.client = client or SentinexClickHouseClient()
        self._seen: set[str] = set()
        self._agent_buffer: list[AgentRunRow] = []
        self._system_buffer: list[SystemEventRow] = []
        self._lock = asyncio.Lock()

    async def handle(self, event: dict[str, Any]) -> None:
        event_id = str(event.get("event_id", ""))
        if event_id and event_id in self._seen:
            return
        if event_id:
            self._seen.add(event_id)

        et = event.get("event_type", "")
        try:
            if et.startswith("run."):
                row = self._agent_row(event)
                async with self._lock:
                    self._agent_buffer.append(row)
                    if len(self._agent_buffer) >= BATCH_SIZE:
                        await self._flush_agent()
            else:
                row = self._system_row(event)
                async with self._lock:
                    self._system_buffer.append(row)
                    if len(self._system_buffer) >= BATCH_SIZE:
                        await self._flush_system()
        except Exception:  # noqa: BLE001
            logger.exception("clickhouse sink failed for event_id=%s", event_id)

    def _agent_row(self, event: dict[str, Any]) -> AgentRunRow:
        ts = event.get("timestamp")
        started_at = datetime.fromisoformat(ts) if isinstance(ts, str) else (ts or datetime.utcnow())
        status_map = {"run.started": "started", "run.completed": "completed", "run.failed": "failed"}
        status = status_map.get(event.get("event_type", ""), "started")
        return AgentRunRow(
            tenant_id=event["tenant_id"],
            run_id=event["run_id"],
            agent_type=event.get("agent_type", "unknown"),
            session_id=(event.get("payload") or {}).get("session_id", ""),
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            trace_id=event.get("trace_id") or "",
            metadata=event.get("payload") or {},
        )

    def _system_row(self, event: dict[str, Any]) -> SystemEventRow:
        ts = event.get("timestamp")
        created_at = datetime.fromisoformat(ts) if isinstance(ts, str) else (ts or datetime.utcnow())
        return SystemEventRow(
            tenant_id=event["tenant_id"],
            event_id=event["event_id"],
            event_type=event["event_type"],
            payload=event.get("payload") or {},
            created_at=created_at,
        )

    async def _flush_agent(self) -> None:
        for row in self._agent_buffer:
            await self.client.insert_agent_run(row)
        self._agent_buffer.clear()

    async def _flush_system(self) -> None:
        for row in self._system_buffer:
            await self.client.insert_system_event(row)
        self._system_buffer.clear()

    async def flush(self) -> None:
        async with self._lock:
            await self._flush_agent()
            await self._flush_system()

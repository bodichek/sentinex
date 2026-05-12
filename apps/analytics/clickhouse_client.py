"""Async-friendly wrapper around clickhouse-connect.

clickhouse-connect itself is sync; we expose `async def` methods that delegate
to a thread executor so callers in async paths (Kafka consumer, LangGraph
nodes) don't block the event loop.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import TYPE_CHECKING, Any

from django.conf import settings

from apps.analytics.schemas import (
    AgentMetricRow,
    AgentRunRow,
    LlmCallRow,
    SystemEventRow,
    TenantUsageSummary,
)

if TYPE_CHECKING:  # pragma: no cover
    from clickhouse_connect.driver.client import Client

DEFAULT_DATABASE = "sentinex"


class SentinexClickHouseClient:
    """Tenant-aware analytics client."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def _get_client(self) -> Client:
        if self._client is None:
            import clickhouse_connect

            self._client = clickhouse_connect.get_client(
                host=getattr(settings, "CLICKHOUSE_HOST", "localhost"),
                port=int(getattr(settings, "CLICKHOUSE_PORT", 8123)),
                database=getattr(settings, "CLICKHOUSE_DATABASE", DEFAULT_DATABASE),
                username=getattr(settings, "CLICKHOUSE_USER", "default"),
                password=getattr(settings, "CLICKHOUSE_PASSWORD", ""),
            )
        return self._client

    async def _to_thread(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, *args, **kwargs)

    # ---- writes ----------------------------------------------------------

    async def insert_agent_run(self, run: AgentRunRow) -> None:
        client = self._get_client()
        row = [
            run.tenant_id,
            str(run.run_id),
            run.agent_type,
            run.session_id,
            run.status,
            run.started_at,
            run.completed_at or run.started_at,
            run.duration_ms,
            run.input_tokens,
            run.output_tokens,
            run.total_cost_usd,
            run.trace_id,
            json.dumps(run.metadata),
        ]
        await self._to_thread(
            client.insert,
            "agent_runs",
            [row],
            column_names=[
                "tenant_id", "run_id", "agent_type", "session_id", "status",
                "started_at", "completed_at", "duration_ms",
                "input_tokens", "output_tokens", "total_cost_usd",
                "trace_id", "metadata",
            ],
        )

    async def insert_llm_call(self, call: LlmCallRow) -> None:
        client = self._get_client()
        row = [
            call.tenant_id, str(call.run_id), str(call.call_id), call.model,
            call.input_tokens, call.output_tokens, call.latency_ms,
            call.cost_usd, call.called_at, call.trace_id,
        ]
        await self._to_thread(
            client.insert,
            "llm_calls",
            [row],
            column_names=[
                "tenant_id", "run_id", "call_id", "model",
                "input_tokens", "output_tokens", "latency_ms",
                "cost_usd", "called_at", "trace_id",
            ],
        )

    async def insert_system_event(self, event: SystemEventRow) -> None:
        client = self._get_client()
        row = [
            event.tenant_id,
            str(event.event_id),
            event.event_type,
            json.dumps(event.payload),
            event.created_at,
        ]
        await self._to_thread(
            client.insert,
            "system_events",
            [row],
            column_names=[
                "tenant_id", "event_id", "event_type", "payload", "created_at"
            ],
        )

    # ---- reads -----------------------------------------------------------

    async def get_tenant_usage(
        self,
        tenant_id: str,
        from_date: date,
        to_date: date,
    ) -> TenantUsageSummary:
        client = self._get_client()
        sql = """
            SELECT
                count() AS runs,
                sum(input_tokens) AS in_tokens,
                sum(output_tokens) AS out_tokens,
                sum(total_cost_usd) AS cost
            FROM agent_runs
            WHERE tenant_id = {tid:String}
              AND started_at >= {f:Date}
              AND started_at < addDays({t:Date}, 1)
        """
        params = {"tid": tenant_id, "f": from_date, "t": to_date}
        result = await self._to_thread(client.query, sql, parameters=params)
        runs, in_tok, out_tok, cost = (result.first_row or (0, 0, 0, 0.0))

        sql_by_type = """
            SELECT agent_type, count() AS runs
            FROM agent_runs
            WHERE tenant_id = {tid:String}
              AND started_at >= {f:Date}
              AND started_at < addDays({t:Date}, 1)
            GROUP BY agent_type
        """
        by_type_res = await self._to_thread(client.query, sql_by_type, parameters=params)
        by_type = {row[0]: int(row[1]) for row in by_type_res.result_rows}

        return TenantUsageSummary(
            tenant_id=tenant_id,
            period_from=from_date,
            period_to=to_date,
            agent_runs=int(runs or 0),
            total_input_tokens=int(in_tok or 0),
            total_output_tokens=int(out_tok or 0),
            total_cost_usd=float(cost or 0.0),
            by_agent_type=by_type,
        )

    async def get_agent_metrics(
        self,
        tenant_id: str,
        agent_type: str | None = None,
        period: str = "7d",
    ) -> list[AgentMetricRow]:
        client = self._get_client()
        days = int(period.rstrip("d") or 7)
        sql = """
            SELECT
                agent_type,
                count() AS runs,
                avg(duration_ms) AS avg_dur,
                avgIf(1, status = 'failed') AS failure_rate,
                sum(total_cost_usd) AS cost
            FROM agent_runs
            WHERE tenant_id = {tid:String}
              AND started_at >= now() - INTERVAL {d:UInt32} DAY
              {filter}
            GROUP BY agent_type
            ORDER BY runs DESC
        """
        params: dict[str, Any] = {"tid": tenant_id, "d": days}
        filter_clause = ""
        if agent_type:
            filter_clause = "AND agent_type = {agent:String}"
            params["agent"] = agent_type
        sql = sql.replace("{filter}", filter_clause)
        res = await self._to_thread(client.query, sql, parameters=params)
        return [
            AgentMetricRow(
                agent_type=row[0],
                runs=int(row[1]),
                avg_duration_ms=float(row[2] or 0.0),
                failure_rate=float(row[3] or 0.0),
                total_cost_usd=float(row[4] or 0.0),
            )
            for row in res.result_rows
        ]

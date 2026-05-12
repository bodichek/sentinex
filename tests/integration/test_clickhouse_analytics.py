"""Integration: ClickHouse insert → query round-trip."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration]


def _ensure_schema() -> None:
    """Idempotent schema bootstrap so the test does not rely on migrations."""
    import clickhouse_connect
    from django.conf import settings

    db = settings.CLICKHOUSE_DATABASE
    cli = clickhouse_connect.get_client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        username=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )
    try:
        cli.command(f"CREATE DATABASE IF NOT EXISTS {db}")
        cli.command(f"USE {db}")
        cli.command(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                tenant_id       String,
                run_id          UUID,
                agent_type      String,
                session_id      String,
                status          Enum8('started'=1,'completed'=2,'failed'=3),
                started_at      DateTime64(3),
                completed_at    DateTime64(3) DEFAULT toDateTime64(0,3),
                duration_ms     UInt32 DEFAULT 0,
                input_tokens    UInt32 DEFAULT 0,
                output_tokens   UInt32 DEFAULT 0,
                total_cost_usd  Float32 DEFAULT 0,
                trace_id        String DEFAULT '',
                metadata        String DEFAULT '{}'
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(started_at)
            ORDER BY (tenant_id, started_at, run_id)
            """
        )
    finally:
        cli.close()


def test_clickhouse_insert_and_aggregate(
    clickhouse_available: bool, integration_tenant_id: str
) -> None:
    if not clickhouse_available:
        pytest.skip("clickhouse not reachable")
    _ensure_schema()

    from apps.analytics.clickhouse_client import SentinexClickHouseClient
    from apps.analytics.schemas import AgentRunRow

    client = SentinexClickHouseClient()

    rows = [
        AgentRunRow(
            tenant_id=integration_tenant_id,
            run_id=uuid4(),
            agent_type="research",
            session_id="itest",
            status="completed",
            started_at=datetime.now(UTC),
            input_tokens=100,
            output_tokens=50,
            total_cost_usd=0.01,
        )
        for _ in range(3)
    ]

    async def _run() -> None:
        for r in rows:
            await client.insert_agent_run(r)

    asyncio.run(_run())

    today = datetime.now(UTC).date()
    summary = asyncio.run(
        client.get_tenant_usage(integration_tenant_id, today, today)
    )
    assert summary.agent_runs >= 3
    assert summary.total_input_tokens >= 300
    assert summary.by_agent_type.get("research", 0) >= 3


def test_clickhouse_isolates_other_tenants(clickhouse_available: bool) -> None:
    if not clickhouse_available:
        pytest.skip("clickhouse not reachable")
    _ensure_schema()

    from apps.analytics.clickhouse_client import SentinexClickHouseClient

    client = SentinexClickHouseClient()
    today = date.today()
    summary = asyncio.run(
        client.get_tenant_usage("nonexistent_tenant_xyz", today, today)
    )
    assert summary.agent_runs == 0

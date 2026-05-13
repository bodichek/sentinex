"""Tests for the ClickHouse client wrapper (mocked driver)."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from apps.analytics.clickhouse_client import SentinexClickHouseClient
from apps.analytics.schemas import AgentRunRow, LlmCallRow


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


def _mk_run(**over: Any) -> AgentRunRow:
    base = {
        "tenant_id": "t1",
        "run_id": uuid4(),
        "agent_type": "research",
        "session_id": "s1",
        "status": "completed",
        "started_at": datetime.now(UTC),
    }
    base.update(over)
    return AgentRunRow.model_validate(base)


def test_insert_agent_run_passes_columns_and_row() -> None:
    fake = MagicMock()
    client = SentinexClickHouseClient(client=fake)
    _run(client.insert_agent_run(_mk_run()))
    fake.insert.assert_called_once()
    args, kwargs = fake.insert.call_args
    assert args[0] == "agent_runs"
    cols = kwargs["column_names"]
    assert "tenant_id" in cols and "run_id" in cols and "metadata" in cols
    assert len(args[1]) == 1
    assert len(args[1][0]) == len(cols)


def test_insert_llm_call_serialises_uuids_to_strings() -> None:
    fake = MagicMock()
    client = SentinexClickHouseClient(client=fake)
    call = LlmCallRow(
        tenant_id="t1",
        run_id=uuid4(),
        call_id=uuid4(),
        model="claude-haiku-4-5",
        input_tokens=100,
        output_tokens=50,
        latency_ms=300,
        cost_usd=0.01,
        called_at=datetime.now(UTC),
    )
    _run(client.insert_llm_call(call))
    args, _ = fake.insert.call_args
    row = args[1][0]
    assert isinstance(row[1], str) and isinstance(row[2], str)


def test_get_tenant_usage_aggregates_two_queries() -> None:
    fake = MagicMock()
    fake.query.side_effect = [
        MagicMock(first_row=(7, 1000, 500, 0.42)),
        MagicMock(result_rows=[("research", 5), ("ops", 2)]),
    ]
    client = SentinexClickHouseClient(client=fake)
    summary = _run(client.get_tenant_usage("t1", date(2026, 1, 1), date(2026, 1, 31)))
    assert summary.agent_runs == 7
    assert summary.total_input_tokens == 1000
    assert summary.total_cost_usd == 0.42
    assert summary.by_agent_type == {"research": 5, "ops": 2}


def test_get_tenant_usage_isolates_by_tenant_param() -> None:
    fake = MagicMock()
    fake.query.side_effect = [
        MagicMock(first_row=(0, 0, 0, 0.0)),
        MagicMock(result_rows=[]),
    ]
    client = SentinexClickHouseClient(client=fake)
    _run(client.get_tenant_usage("tenant-x", date(2026, 1, 1), date(2026, 1, 31)))
    first_call = fake.query.call_args_list[0]
    assert first_call.kwargs["parameters"]["tid"] == "tenant-x"

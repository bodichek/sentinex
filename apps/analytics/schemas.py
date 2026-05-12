"""Pydantic row types for analytics writes/reads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunRow(BaseModel):
    tenant_id: str
    run_id: UUID
    agent_type: str
    session_id: str
    status: Literal["started", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class LlmCallRow(BaseModel):
    tenant_id: str
    run_id: UUID
    call_id: UUID
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    called_at: datetime
    trace_id: str = ""


class SystemEventRow(BaseModel):
    tenant_id: str
    event_id: UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TenantUsageSummary(BaseModel):
    tenant_id: str
    period_from: date
    period_to: date
    agent_runs: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_agent_type: dict[str, int] = Field(default_factory=dict)


class AgentMetricRow(BaseModel):
    agent_type: str
    runs: int
    avg_duration_ms: float
    failure_rate: float
    total_cost_usd: float

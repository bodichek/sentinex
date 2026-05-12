"""Pydantic schemas for the Kafka event bus."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    AGENT = "agent"
    SYSTEM = "system"
    USER = "user"


class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentRunEvent(BaseEvent):
    """Lifecycle event for a LangGraph agent run."""

    agent_type: str
    run_id: UUID
    event_type: Literal[
        "run.started",
        "run.completed",
        "run.failed",
        "run.step.completed",
    ]
    trace_id: str | None = None


class SystemEvent(BaseEvent):
    event_type: Literal[
        "tenant.created",
        "tenant.suspended",
        "addon.enabled",
        "addon.disabled",
    ]


class UserEvent(BaseEvent):
    event_type: Literal["user.created", "user.login", "user.action"]
    user_id: int | None = None


def category_of(event: BaseEvent) -> EventCategory:
    if isinstance(event, AgentRunEvent):
        return EventCategory.AGENT
    if isinstance(event, SystemEvent):
        return EventCategory.SYSTEM
    if isinstance(event, UserEvent):
        return EventCategory.USER
    raise ValueError(f"Unknown event class: {type(event).__name__}")

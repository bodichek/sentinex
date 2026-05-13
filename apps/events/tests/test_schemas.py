"""Tests for the event Pydantic schemas."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.events.schemas import (
    AgentRunEvent,
    EventCategory,
    SystemEvent,
    UserEvent,
    category_of,
)


def test_agent_event_validates_run_lifecycle_types() -> None:
    evt = AgentRunEvent(
        tenant_id="t1",
        agent_type="research",
        run_id=uuid4(),
        event_type="run.started",
    )
    assert evt.event_type == "run.started"
    assert evt.timestamp is not None


def test_agent_event_rejects_unknown_event_type() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AgentRunEvent(
            tenant_id="t1",
            agent_type="research",
            run_id=uuid4(),
            event_type="run.bogus",  # type: ignore[arg-type]
        )


def test_system_event_round_trips_through_json() -> None:
    evt = SystemEvent(tenant_id="t1", event_type="tenant.created")
    payload = evt.model_dump_json()
    parsed = SystemEvent.model_validate_json(payload)
    assert parsed.event_type == "tenant.created"


def test_category_of_dispatches_each_event_kind() -> None:
    assert category_of(
        AgentRunEvent(
            tenant_id="t", agent_type="r", run_id=uuid4(), event_type="run.started"
        )
    ) is EventCategory.AGENT
    assert category_of(SystemEvent(tenant_id="t", event_type="tenant.created")) is EventCategory.SYSTEM
    assert category_of(UserEvent(tenant_id="t", event_type="user.login")) is EventCategory.USER

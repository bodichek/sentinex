"""Tests for topic naming + provisioning."""

from __future__ import annotations

from apps.events.topic_manager import (
    DEFAULT_CATEGORIES,
    sanitize_tenant_id,
    topic_for,
    topics_for_tenant,
)


def test_topic_naming_follows_convention() -> None:
    assert topic_for("acme", "agent") == "acme.events.agent"


def test_tenant_id_is_sanitised() -> None:
    assert sanitize_tenant_id("Tenant 1/42") == "Tenant_1_42"
    assert sanitize_tenant_id("") == "default"


def test_topics_for_tenant_covers_all_categories() -> None:
    topics = topics_for_tenant("acme")
    assert len(topics) == len(DEFAULT_CATEGORIES)
    for cat in DEFAULT_CATEGORIES:
        assert any(t.endswith(f".events.{cat}") for t in topics)


def test_topics_isolate_between_tenants() -> None:
    a = set(topics_for_tenant("a"))
    b = set(topics_for_tenant("b"))
    assert a.isdisjoint(b)

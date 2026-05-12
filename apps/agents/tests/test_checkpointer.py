"""Tests for the tenant-scoped Redis checkpointer wrapper."""

from __future__ import annotations

from apps.agents.checkpointers import checkpoint_config, thread_id_for


def test_thread_id_includes_all_scopes() -> None:
    assert thread_id_for("t1", "research", "s1") == "t1:research:s1"


def test_checkpoint_config_isolates_by_tenant() -> None:
    a = checkpoint_config("tenant_a", "research", "s1")
    b = checkpoint_config("tenant_b", "research", "s1")
    assert a["configurable"]["thread_id"] != b["configurable"]["thread_id"]


def test_checkpoint_config_includes_ttl_when_provided() -> None:
    cfg = checkpoint_config("t1", "agent", "s1", ttl_seconds=60)
    assert cfg["configurable"]["ttl"] == 60

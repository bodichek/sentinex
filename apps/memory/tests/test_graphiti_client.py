"""Tests for :mod:`apps.memory.graphiti_client`."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.memory.graphiti_client import TenantGraphitiClient, _tenant_group_id


def test_tenant_group_id_sanitises_special_chars() -> None:
    assert _tenant_group_id("tenant-a") == "tenant-a"
    assert _tenant_group_id("tenant a/42") == "tenant_a_42"
    assert _tenant_group_id("") == "default"


def test_tenant_group_id_isolates_between_tenants() -> None:
    assert _tenant_group_id("a") != _tenant_group_id("b")


@pytest.mark.parametrize("tenant_id", ["alpha", "tenant-7"])
def test_add_episode_passes_group_id(tenant_id: str) -> None:
    fake = MagicMock()
    fake.add_episode = AsyncMock(return_value="ok")
    client = TenantGraphitiClient(graphiti=fake)

    result = asyncio.run(client.add_episode(tenant_id, "hello"))

    assert result == "ok"
    kwargs: dict[str, Any] = fake.add_episode.await_args.kwargs
    assert kwargs["group_id"] == _tenant_group_id(tenant_id)
    assert kwargs["episode_body"] == "hello"


def test_search_isolates_results_by_group_id() -> None:
    fake = MagicMock()
    fake.search = AsyncMock(return_value=["edge1"])
    client = TenantGraphitiClient(graphiti=fake)

    results = asyncio.run(client.search("tenant-x", "query", num_results=3))

    assert results == ["edge1"]
    kwargs = fake.search.await_args.kwargs
    assert kwargs["group_ids"] == [_tenant_group_id("tenant-x")]
    assert kwargs["num_results"] == 3


def test_search_does_not_leak_between_tenants() -> None:
    fake = MagicMock()
    fake.search = AsyncMock(return_value=[])
    client = TenantGraphitiClient(graphiti=fake)

    asyncio.run(client.search("a", "q"))
    asyncio.run(client.search("b", "q"))

    group_ids = [
        call.kwargs["group_ids"] for call in fake.search.await_args_list
    ]
    assert group_ids[0] != group_ids[1]

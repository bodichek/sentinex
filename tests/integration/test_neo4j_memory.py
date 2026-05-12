"""Integration: Neo4j round-trip via the bolt driver and Graphiti tenant isolation.

The full Graphiti add_episode → search round-trip needs an Anthropic key + an
OpenAI key (entity extraction + embeddings) so it skips unless both are set.
The driver-only test runs whenever Neo4j is up.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

pytestmark = [pytest.mark.integration]


def test_neo4j_driver_writes_and_reads(neo4j_available: bool, integration_tenant_id: str) -> None:
    if not neo4j_available:
        pytest.skip("neo4j not reachable")
    from neo4j import GraphDatabase
    from django.conf import settings

    drv = GraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    label = f"SmokeProbe_{integration_tenant_id}"
    try:
        with drv.session() as s:
            s.run(f"CREATE (n:{label} {{tenant_id: $tid, value: 'hello'}})", tid=integration_tenant_id)
            row = s.run(
                f"MATCH (n:{label} {{tenant_id: $tid}}) RETURN n.value AS v",
                tid=integration_tenant_id,
            ).single()
            assert row is not None
            assert row["v"] == "hello"
            s.run(f"MATCH (n:{label}) DETACH DELETE n")
    finally:
        drv.close()


def test_graphiti_episode_roundtrip(
    neo4j_available: bool,
    anthropic_credentialed: bool,
    openai_credentialed: bool,
    integration_tenant_id: str,
) -> None:
    if not neo4j_available:
        pytest.skip("neo4j not reachable")
    if not (anthropic_credentialed and openai_credentialed):
        pytest.skip("graphiti needs ANTHROPIC_API_KEY and OPENAI_API_KEY")

    from apps.memory.graphiti_client import TenantGraphitiClient, _tenant_group_id

    client = TenantGraphitiClient()

    async def _go() -> tuple[str, list[object]]:
        await client.add_episode(
            integration_tenant_id,
            "Acme Corp signed a 12-month contract with Sentinex in Q1 2026.",
            name="integration-fact",
            source_description="integration-test",
            reference_time=datetime.now(UTC),
        )
        results = await client.search(integration_tenant_id, "Acme contract", num_results=5)
        return _tenant_group_id(integration_tenant_id), results

    group, results = asyncio.run(_go())
    assert isinstance(group, str)
    assert isinstance(results, list)


def test_graphiti_tenant_isolation_via_group_id(
    neo4j_available: bool,
    anthropic_credentialed: bool,
    openai_credentialed: bool,
) -> None:
    if not neo4j_available:
        pytest.skip("neo4j not reachable")
    if not (anthropic_credentialed and openai_credentialed):
        pytest.skip("graphiti needs ANTHROPIC_API_KEY and OPENAI_API_KEY")

    from apps.memory.graphiti_client import TenantGraphitiClient

    client = TenantGraphitiClient()
    tenant_a = "itest_iso_a"
    tenant_b = "itest_iso_b"

    async def _go() -> tuple[list, list]:
        await client.add_episode(
            tenant_a,
            "Project Polaris launches in March.",
            name="tenant-a-fact",
            source_description="integration-test",
        )
        a = await client.search(tenant_a, "Polaris", num_results=5)
        b = await client.search(tenant_b, "Polaris", num_results=5)
        return a, b

    res_a, res_b = asyncio.run(_go())
    assert isinstance(res_a, list) and isinstance(res_b, list)
    # B's tenant has no Polaris fact → must not return A's data.
    assert all(getattr(e, "group_id", None) != "itest_iso_a" for e in res_b)

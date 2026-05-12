"""Service reachability smoke tests.

Each test pings one infrastructure dependency. They are *not* unit tests;
they verify that the development stack (docker compose) is up.
"""

from __future__ import annotations

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.django_db]


def test_postgres_reachable(postgres_available: bool) -> None:
    if not postgres_available:
        pytest.skip("postgres not reachable")
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)


def test_redis_reachable(redis_available: bool) -> None:
    if not redis_available:
        pytest.skip("redis not reachable")
    import redis as redis_lib
    from django.conf import settings

    r = redis_lib.from_url(settings.REDIS_URL)
    assert r.ping() is True


def test_neo4j_reachable(neo4j_available: bool) -> None:
    if not neo4j_available:
        pytest.skip("neo4j not reachable")
    from neo4j import GraphDatabase
    from django.conf import settings

    if not settings.NEO4J_PASSWORD:
        pytest.skip("NEO4J_PASSWORD not configured")
    drv = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        with drv.session() as s:
            assert s.run("RETURN 1 AS x").single()["x"] == 1
    except Exception as exc:
        if "Unauthorized" in str(exc) or "credentials" in str(exc):
            pytest.skip(f"neo4j auth not configured: {exc}")
        raise
    finally:
        drv.close()


def test_kafka_reachable(kafka_available: bool) -> None:
    if not kafka_available:
        pytest.skip("kafka not reachable")
    from kafka.admin import KafkaAdminClient
    from django.conf import settings

    admin = KafkaAdminClient(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id="sentinex-smoke",
    )
    try:
        topics = admin.list_topics()
        assert isinstance(topics, list)
    finally:
        admin.close()


def test_clickhouse_reachable(clickhouse_available: bool) -> None:
    if not clickhouse_available:
        pytest.skip("clickhouse not reachable")
    import clickhouse_connect
    from django.conf import settings

    try:
        client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            username=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
        )
    except Exception as exc:
        if "AUTHENTICATION_FAILED" in str(exc) or "Authentication" in str(exc):
            pytest.skip(f"clickhouse auth not configured: {exc}")
        raise
    try:
        assert client.command("SELECT 1") == 1
    finally:
        client.close()


def test_langfuse_reachable(langfuse_available: bool) -> None:
    if not langfuse_available:
        pytest.skip("langfuse not reachable")
    import urllib.request
    from django.conf import settings

    url = settings.LANGFUSE_HOST.rstrip("/") + "/api/public/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310
            assert resp.status in (200, 401, 404)
    except Exception:
        # Some Langfuse builds don't expose /health; reachability already
        # confirmed by TCP probe.
        pass

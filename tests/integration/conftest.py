"""Fixtures and gating helpers for integration tests."""

from __future__ import annotations

import socket
import uuid
from urllib.parse import urlparse

import pytest


def _tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def neo4j_available() -> bool:
    from django.conf import settings

    parsed = urlparse(getattr(settings, "NEO4J_URI", "bolt://localhost:7687"))
    return _tcp_open(parsed.hostname or "localhost", parsed.port or 7687)


@pytest.fixture(scope="session")
def kafka_available() -> bool:
    from django.conf import settings

    bs = getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    host, _, port = bs.partition(":")
    return _tcp_open(host or "localhost", int(port or 9092))


@pytest.fixture(scope="session")
def clickhouse_available() -> bool:
    from django.conf import settings

    return _tcp_open(
        getattr(settings, "CLICKHOUSE_HOST", "localhost"),
        int(getattr(settings, "CLICKHOUSE_PORT", 8123)),
    )


@pytest.fixture(scope="session")
def anthropic_credentialed() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


@pytest.fixture(scope="session")
def openai_credentialed() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "OPENAI_API_KEY", ""))


@pytest.fixture
def integration_tenant_id() -> str:
    return f"itest{uuid.uuid4().hex[:10]}"

"""Shared helpers for smoke tests.

Each smoke test should skip — never fail — when its target service is not
configured or unreachable. The fixtures here provide the gating decisions.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest


def _tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _env_truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).lower() in {"1", "true", "yes", "on"}


def _require_tcp(host: str, port: int, label: str) -> None:
    if not _tcp_open(host, port):
        pytest.skip(f"{label} not reachable at {host}:{port}")


@pytest.fixture(scope="session")
def postgres_available() -> bool:
    from django.conf import settings

    db = settings.DATABASES.get("default", {})
    host = db.get("HOST") or "localhost"
    port = int(db.get("PORT") or 5432)
    return _tcp_open(host, port)


@pytest.fixture(scope="session")
def redis_available() -> bool:
    from django.conf import settings

    parsed = urlparse(getattr(settings, "REDIS_URL", "redis://localhost:6379/0"))
    return _tcp_open(parsed.hostname or "localhost", parsed.port or 6379)


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

    host = getattr(settings, "CLICKHOUSE_HOST", "localhost")
    port = int(getattr(settings, "CLICKHOUSE_PORT", 8123))
    return _tcp_open(host, port)


@pytest.fixture(scope="session")
def langfuse_available() -> bool:
    from django.conf import settings

    parsed = urlparse(getattr(settings, "LANGFUSE_HOST", "http://localhost:3000"))
    return _tcp_open(parsed.hostname or "localhost", parsed.port or 3000)


@pytest.fixture(scope="session")
def langfuse_credentialed(langfuse_available: bool) -> bool:
    from django.conf import settings

    return bool(
        langfuse_available
        and getattr(settings, "LANGFUSE_ENABLED", False)
        and getattr(settings, "LANGFUSE_PUBLIC_KEY", "")
        and getattr(settings, "LANGFUSE_SECRET_KEY", "")
    )

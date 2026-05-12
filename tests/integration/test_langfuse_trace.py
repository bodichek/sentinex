"""Integration: Langfuse trace creation."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

import pytest

pytestmark = [pytest.mark.integration]


def test_langfuse_trace_create() -> None:
    from django.conf import settings

    if not getattr(settings, "LANGFUSE_ENABLED", False):
        pytest.skip("LANGFUSE_ENABLED=false")
    parsed = urlparse(settings.LANGFUSE_HOST)
    try:
        with socket.create_connection(
            (parsed.hostname or "localhost", parsed.port or 3000), 1.5
        ):
            pass
    except OSError:
        pytest.skip("langfuse not reachable")
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        pytest.skip("langfuse keys not configured")

    from apps.observability.langfuse_client import SentinexLangfuseClient

    client = SentinexLangfuseClient()
    trace = client.trace(
        tenant_id="itest_lf",
        name="integration-trace",
        input={"q": "ping"},
        output={"a": "pong"},
        metadata={"source": "integration-test"},
    )
    assert trace is not None
    assert getattr(trace, "id", None)

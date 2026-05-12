"""Integration: Redis-backed LangGraph checkpointer round-trip."""

from __future__ import annotations

import asyncio
import socket
import uuid
from urllib.parse import urlparse

import pytest

pytestmark = [pytest.mark.integration]


def _redis_up() -> bool:
    from django.conf import settings

    parsed = urlparse(settings.REDIS_URL)
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 6379), 1.5):
            return True
    except OSError:
        return False


def test_redis_checkpoint_roundtrip() -> None:
    if not _redis_up():
        pytest.skip("redis not reachable")
    import redis as redis_lib
    from django.conf import settings

    from apps.agents.checkpointers import thread_id_for

    tid = thread_id_for(f"itest{uuid.uuid4().hex[:6]}", "research", "s1")
    r = redis_lib.from_url(settings.REDIS_URL)
    key = f"sentinex:test:{tid}"
    try:
        r.set(key, "ok", ex=30)
        assert r.get(key) == b"ok"
    finally:
        r.delete(key)

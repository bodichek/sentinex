"""Redis checkpointer wrapper for LangGraph state persistence.

Thread IDs are tenant-scoped: ``{tenant_id}:{agent_id}:{session_id}``.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings


def thread_id_for(tenant_id: str, agent_id: str, session_id: str) -> str:
    """Build a tenant-isolated thread id for the checkpointer."""
    return f"{tenant_id}:{agent_id}:{session_id}"


def checkpoint_config(
    tenant_id: str,
    agent_id: str,
    session_id: str,
    *,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    """Build a LangGraph runnable config with tenant-scoped thread id."""
    cfg: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id_for(tenant_id, agent_id, session_id),
        }
    }
    if ttl_seconds:
        cfg["configurable"]["ttl"] = ttl_seconds
    return cfg


async def get_redis_checkpointer() -> Any:
    """Return an ``AsyncRedisSaver`` configured against the project Redis."""
    from langgraph.checkpoint.redis.aio import AsyncRedisSaver

    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    saver = AsyncRedisSaver(redis_url=redis_url)
    await saver.asetup()
    return saver

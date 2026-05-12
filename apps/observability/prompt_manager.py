"""Prompt registry backed by Langfuse with a Redis cache + local fallback."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

from apps.observability.langfuse_client import get_client

logger = logging.getLogger("sentinex.observability.prompts")

CACHE_TTL_SECONDS = 5 * 60
LOCAL_PROMPTS_DIR = Path(settings.BASE_DIR) / "apps" / "agents" / "prompts"


def _cache_key(name: str, version: int | None) -> str:
    return f"prompts:{name}:{version or 'latest'}"


def _local_fallback(name: str) -> str | None:
    candidate = LOCAL_PROMPTS_DIR / f"{name}.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return None


async def get_prompt(name: str, version: int | None = None) -> str:
    """Return a prompt body, preferring Langfuse, falling back to local file."""
    key = _cache_key(name, version)
    cached = cache.get(key)
    if cached:
        return cached  # type: ignore[no-any-return]

    client = get_client()
    sdk = client._get_sdk()  # noqa: SLF001 — internal helper, intentional
    if sdk is not None:
        try:
            prompt = await asyncio.to_thread(
                sdk.get_prompt, name, version=version
            )
            content: str = getattr(prompt, "prompt", "") or str(prompt)
            cache.set(key, content, CACHE_TTL_SECONDS)
            return content
        except Exception:  # noqa: BLE001
            logger.warning("Langfuse get_prompt failed; using local fallback")

    local = _local_fallback(name)
    if local is not None:
        cache.set(key, local, CACHE_TTL_SECONDS)
        return local
    raise FileNotFoundError(f"prompt not found: {name}")


async def push_prompt(name: str, content: str, labels: list[str] | None = None) -> None:
    client = get_client()
    sdk = client._get_sdk()  # noqa: SLF001
    if sdk is None:
        logger.info("Langfuse disabled; push_prompt is a no-op for %s", name)
        return
    await asyncio.to_thread(
        sdk.create_prompt, name=name, prompt=content, labels=labels or []
    )
    cache.delete(_cache_key(name, None))

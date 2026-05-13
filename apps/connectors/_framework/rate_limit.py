"""Redis-backed token bucket for per-provider rate limiting.

Usage:
    bucket = TokenBucket("pipedrive", capacity=100, refill_per_sec=50)
    bucket.acquire(1)  # blocks until a token is available, raises on timeout
"""

from __future__ import annotations

import time

from django.core.cache import cache


class RateLimitTimeout(RuntimeError):
    pass


class TokenBucket:
    """Simple cache-based token bucket. Atomicity is approximate — good enough
    for connector ingest where we have one Celery worker pool per provider.

    For strict atomicity across many workers, swap implementation for
    a Lua script on Redis via django_redis.get_redis_connection.
    """

    def __init__(
        self,
        key: str,
        *,
        capacity: int,
        refill_per_sec: float,
        cache_alias: str = "default",
    ) -> None:
        self.key = f"ratelimit:{key}"
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.cache = cache

    def _now(self) -> float:
        return time.monotonic()

    def _state(self) -> tuple[float, float]:
        state = self.cache.get(self.key)
        if state is None:
            return float(self.capacity), self._now()
        tokens, last = state
        return float(tokens), float(last)

    def _save(self, tokens: float, ts: float) -> None:
        self.cache.set(self.key, (tokens, ts), timeout=3600)

    def acquire(self, tokens: int = 1, *, timeout_sec: float = 30.0) -> None:
        deadline = self._now() + timeout_sec
        while True:
            cur_tokens, last = self._state()
            now = self._now()
            cur_tokens = min(self.capacity, cur_tokens + (now - last) * self.refill_per_sec)
            if cur_tokens >= tokens:
                self._save(cur_tokens - tokens, now)
                return
            if now >= deadline:
                raise RateLimitTimeout(f"timeout waiting for {tokens} tokens on {self.key}")
            wait = (tokens - cur_tokens) / max(self.refill_per_sec, 0.01)
            time.sleep(min(wait, 0.5))

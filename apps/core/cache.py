"""Cache utilities with tenant-aware keys."""

from __future__ import annotations

import hashlib
import json
import pickle
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from django.core.cache import cache
from django.db import connection

F = TypeVar("F", bound=Callable[..., Any])


def _tenant_schema() -> str:
    return getattr(connection, "schema_name", None) or "public"


def cache_result(ttl: int, key_prefix: str) -> Callable[[F], F]:
    """Decorator that caches a function result in Redis under a tenant-scoped key."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            payload = json.dumps(
                {"a": [str(a) for a in args], "k": {str(k): str(v) for k, v in kwargs.items()}},
                sort_keys=True,
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
            key = f"insight:{_tenant_schema()}:{key_prefix}:{digest}"

            cached = cache.get(key)
            if cached is not None:
                return pickle.loads(cached)

            result = func(*args, **kwargs)
            cache.set(key, pickle.dumps(result), ttl)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator

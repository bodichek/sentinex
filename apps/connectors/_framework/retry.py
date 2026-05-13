"""Exponential backoff retry decorator.

Designed for connector calls that may hit transient 5xx, 429, network errors.
Honors a Retry-After hint if the wrapped function raises an exception with
a ``retry_after`` attribute (in seconds).
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    *,
    retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.25,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff.

    - ``retries`` does NOT count the first attempt. So total attempts = retries + 1.
    - If the raised exception has a ``retry_after`` attribute (float seconds),
      that value is used instead of the computed backoff.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt > retries:
                        raise
                    hint = getattr(exc, "retry_after", None)
                    if isinstance(hint, (int, float)) and hint > 0:
                        delay = min(float(hint), max_delay)
                    else:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        delay *= 1 + random.uniform(-jitter, jitter)
                    logger.warning(
                        "retry %s attempt=%s/%s delay=%.2fs err=%s",
                        fn.__name__, attempt, retries, delay, exc,
                    )
                    time.sleep(delay)
        return wrapper

    return decorator

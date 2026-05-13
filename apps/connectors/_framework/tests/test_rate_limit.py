from __future__ import annotations

import time

import pytest

from apps.connectors._framework.rate_limit import RateLimitTimeout, TokenBucket


def test_token_bucket_allows_burst_up_to_capacity() -> None:
    bucket = TokenBucket("test_burst", capacity=5, refill_per_sec=1.0)
    for _ in range(5):
        bucket.acquire(1, timeout_sec=1.0)


def test_token_bucket_times_out_when_starved() -> None:
    bucket = TokenBucket("test_starve", capacity=1, refill_per_sec=0.1)
    bucket.acquire(1, timeout_sec=0.5)
    with pytest.raises(RateLimitTimeout):
        bucket.acquire(5, timeout_sec=0.5)


def test_token_bucket_refills_over_time() -> None:
    bucket = TokenBucket("test_refill", capacity=2, refill_per_sec=20.0)
    bucket.acquire(2)
    time.sleep(0.2)  # should refill ~4 tokens, capped to 2
    bucket.acquire(2, timeout_sec=0.5)

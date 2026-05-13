from __future__ import annotations

import pytest

from apps.connectors._framework.retry import retry_with_backoff


def test_retry_eventually_succeeds() -> None:
    attempts = {"n": 0}

    @retry_with_backoff(retries=3, base_delay=0.01, jitter=0.0)
    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("boom")
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 3


def test_retry_gives_up_after_max() -> None:
    @retry_with_backoff(retries=2, base_delay=0.01, jitter=0.0)
    def always_fails() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        always_fails()


def test_retry_honors_retry_after_hint() -> None:
    class HintedError(RuntimeError):
        retry_after = 0.02

    attempts = {"n": 0}

    @retry_with_backoff(retries=2, base_delay=10.0)
    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise HintedError("rate limited")
        return "ok"

    assert flaky() == "ok"

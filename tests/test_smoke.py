"""Smoke test — verifies the test harness works."""

from __future__ import annotations

import django


def test_django_configured() -> None:
    assert django.VERSION[0] == 5

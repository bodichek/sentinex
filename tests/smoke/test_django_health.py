"""Django-side smoke tests — settings sanity, URL routing, app registry."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def test_required_settings_are_present() -> None:
    from django.conf import settings

    for key in (
        "REDIS_URL",
        "NEO4J_URI",
        "KAFKA_BOOTSTRAP_SERVERS",
        "CLICKHOUSE_HOST",
        "LANGFUSE_HOST",
    ):
        assert hasattr(settings, key), f"missing setting: {key}"


def test_tenant_apps_include_full_stack() -> None:
    from django.conf import settings

    expected = {
        "apps.agents",
        "apps.memory",
        "apps.events",
        "apps.analytics",
        "apps.observability",
        "apps.billing",
    }
    assert expected.issubset(set(settings.INSTALLED_APPS))


def test_api_urls_are_registered() -> None:
    from django.urls import reverse

    for name in (
        "api_query",
        "api_memory_search",
        "api_memory_episode",
        "api_analytics_usage",
        "api_observability_traces",
    ):
        assert reverse(name).startswith("/api/v1/")

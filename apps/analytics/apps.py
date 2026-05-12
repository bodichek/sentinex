"""App config for analytics."""

from __future__ import annotations

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = "apps.analytics"
    label = "analytics"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Sentinex Analytics (ClickHouse)"

"""App config for observability."""

from __future__ import annotations

from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    name = "apps.observability"
    label = "observability"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Sentinex Observability (Langfuse)"

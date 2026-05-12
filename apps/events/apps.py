"""Django app config for the events module."""

from __future__ import annotations

from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "apps.events"
    label = "events"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Sentinex Events (Kafka)"

    def ready(self) -> None:  # pragma: no cover
        from apps.events import signals  # noqa: F401

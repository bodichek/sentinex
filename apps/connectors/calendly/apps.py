from __future__ import annotations

from django.apps import AppConfig


class CalendlyConnectorConfig(AppConfig):
    name = "apps.connectors.calendly"
    label = "connectors_calendly"
    verbose_name = "Calendly connector"

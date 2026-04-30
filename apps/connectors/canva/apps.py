from __future__ import annotations

from django.apps import AppConfig


class CanvaConnectorConfig(AppConfig):
    name = "apps.connectors.canva"
    label = "connectors_canva"
    verbose_name = "Canva connector"

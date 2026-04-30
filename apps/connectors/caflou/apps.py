from __future__ import annotations

from django.apps import AppConfig


class CaflouConnectorConfig(AppConfig):
    name = "apps.connectors.caflou"
    label = "connectors_caflou"
    verbose_name = "Caflou connector"

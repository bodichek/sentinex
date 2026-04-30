from __future__ import annotations

from django.apps import AppConfig


class RaynetConnectorConfig(AppConfig):
    name = "apps.connectors.raynet"
    label = "connectors_raynet"
    verbose_name = "Raynet CRM connector"

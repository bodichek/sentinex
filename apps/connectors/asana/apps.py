from __future__ import annotations

from django.apps import AppConfig


class AsanaConnectorConfig(AppConfig):
    name = "apps.connectors.asana"
    label = "connectors_asana"
    verbose_name = "Asana connector"

from __future__ import annotations

from django.apps import AppConfig


class Microsoft365ConnectorConfig(AppConfig):
    name = "apps.connectors.microsoft365"
    label = "connectors_microsoft365"
    verbose_name = "Microsoft 365 connector"

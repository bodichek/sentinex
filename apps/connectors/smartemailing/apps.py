from __future__ import annotations

from django.apps import AppConfig


class SmartEmailingConnectorConfig(AppConfig):
    name = "apps.connectors.smartemailing"
    label = "connectors_smartemailing"
    verbose_name = "SmartEmailing connector"

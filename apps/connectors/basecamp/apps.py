from __future__ import annotations

from django.apps import AppConfig


class BasecampConnectorConfig(AppConfig):
    name = "apps.connectors.basecamp"
    label = "connectors_basecamp"
    verbose_name = "Basecamp connector"

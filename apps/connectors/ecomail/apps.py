from __future__ import annotations

from django.apps import AppConfig


class EcomailConnectorConfig(AppConfig):
    name = "apps.connectors.ecomail"
    label = "connectors_ecomail"
    verbose_name = "Ecomail connector"

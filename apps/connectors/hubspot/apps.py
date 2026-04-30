from __future__ import annotations

from django.apps import AppConfig


class HubspotConnectorConfig(AppConfig):
    name = "apps.connectors.hubspot"
    label = "connectors_hubspot"
    verbose_name = "HubSpot connector"

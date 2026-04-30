from __future__ import annotations

from django.apps import AppConfig


class FapiConnectorConfig(AppConfig):
    name = "apps.connectors.fapi"
    label = "connectors_fapi"
    verbose_name = "FAPI connector"

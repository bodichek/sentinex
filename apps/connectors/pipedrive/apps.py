from __future__ import annotations

from django.apps import AppConfig


class PipedriveConnectorConfig(AppConfig):
    name = "apps.connectors.pipedrive"
    label = "connectors_pipedrive"
    verbose_name = "Pipedrive connector"

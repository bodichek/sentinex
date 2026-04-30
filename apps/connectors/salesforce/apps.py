from __future__ import annotations

from django.apps import AppConfig


class SalesforceConnectorConfig(AppConfig):
    name = "apps.connectors.salesforce"
    label = "connectors_salesforce"
    verbose_name = "Salesforce connector"

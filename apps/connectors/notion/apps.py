from __future__ import annotations

from django.apps import AppConfig


class NotionConnectorConfig(AppConfig):
    name = "apps.connectors.notion"
    label = "connectors_notion"
    verbose_name = "Notion connector"

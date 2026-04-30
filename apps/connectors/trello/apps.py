from __future__ import annotations

from django.apps import AppConfig


class TrelloConnectorConfig(AppConfig):
    name = "apps.connectors.trello"
    label = "connectors_trello"
    verbose_name = "Trello connector"

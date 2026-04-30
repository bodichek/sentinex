from __future__ import annotations

from django.apps import AppConfig


class SlackConnectorConfig(AppConfig):
    name = "apps.connectors.slack"
    label = "connectors_slack"
    verbose_name = "Slack connector"

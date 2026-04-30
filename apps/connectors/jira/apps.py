from __future__ import annotations

from django.apps import AppConfig


class JiraConnectorConfig(AppConfig):
    name = "apps.connectors.jira"
    label = "connectors_jira"
    verbose_name = "Jira (Atlassian) connector"

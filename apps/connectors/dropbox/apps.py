from __future__ import annotations

from django.apps import AppConfig


class DropboxConnectorConfig(AppConfig):
    name = "apps.connectors.dropbox"
    label = "connectors_dropbox"
    verbose_name = "Dropbox connector"

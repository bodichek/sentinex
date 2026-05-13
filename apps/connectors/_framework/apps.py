from django.apps import AppConfig


class ConnectorFrameworkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.connectors._framework"
    label = "connectors_framework"
    verbose_name = "Connector ingest framework"

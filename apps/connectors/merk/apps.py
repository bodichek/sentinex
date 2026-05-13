from django.apps import AppConfig


class MerkConnectorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.connectors.merk"
    label = "connectors_merk"
    verbose_name = "Merk.cz connector"

from django.apps import AppConfig


class DataAccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.data_access"
    label = "data_access"

    def ready(self) -> None:
        from apps.data_access import signals  # noqa: F401

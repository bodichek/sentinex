from __future__ import annotations

from typing import Any

from django.apps import AppConfig


class WeeklyBriefConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.addons.weekly_brief"
    label = "weekly_brief"

    def on_activate(self, tenant: Any) -> None:
        """Create a default WeeklyBriefConfig record for the tenant."""
        from django_tenants.utils import schema_context

        from apps.addons.weekly_brief.models import WeeklyBriefConfig as ConfigModel

        with schema_context(tenant.schema_name):
            ConfigModel.objects.get_or_create(pk=1, defaults={"recipients": ""})

    def on_deactivate(self, tenant: Any) -> None:
        # Preserve historical reports; do nothing.
        return

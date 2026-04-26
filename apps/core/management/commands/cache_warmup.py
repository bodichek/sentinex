"""Pre-warm caches for every active tenant (run after deploy)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from apps.core.models import Tenant
from apps.data_access.insight_functions import INSIGHT_FUNCTIONS


class Command(BaseCommand):
    help = "Warm Insight Function caches for every active tenant."

    def handle(self, *args: Any, **opts: Any) -> None:
        tenants = Tenant.objects.filter(is_active=True).exclude(schema_name="public")
        for tenant in tenants:
            with schema_context(tenant.schema_name):
                for name, func in INSIGHT_FUNCTIONS.items():
                    try:
                        func()
                        self.stdout.write(f"  warmed {tenant.schema_name}:{name}")
                    except Exception as exc:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  skipped {tenant.schema_name}:{name} ({exc})"
                            )
                        )

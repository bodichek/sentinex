"""Print all tenants with their primary domain and status."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.core.models import Tenant


class Command(BaseCommand):
    help = "List all tenants with schema, primary domain, and active status."

    def handle(self, *args: Any, **options: Any) -> None:
        tenants = Tenant.objects.prefetch_related("domains").order_by("schema_name")
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found."))
            return

        header = f"{'SCHEMA':<20} {'NAME':<30} {'DOMAIN':<40} {'ACTIVE':<6}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for t in tenants:
            domains = list(t.domains.all())
            primary = next((d.domain for d in domains if d.is_primary), "")
            self.stdout.write(
                f"{t.schema_name:<20} {t.name[:30]:<30} {primary:<40} {t.is_active!s:<6}"
            )

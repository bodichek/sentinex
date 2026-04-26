"""Ensure the 'public' tenant and its default domain exist.

Idempotent: safe to run repeatedly. Intended to run once after
``migrate_schemas --shared``.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.models import Domain, Tenant


class Command(BaseCommand):
    help = "Create the default 'public' tenant (shared-schema marker) if missing."

    def handle(self, *args: Any, **options: Any) -> None:
        tenant, created = Tenant.objects.get_or_create(
            schema_name=settings.PUBLIC_SCHEMA_NAME,
            defaults={"name": "Public"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created public tenant."))
        else:
            self.stdout.write("Public tenant already exists.")

        tenant_host: str = settings.TENANT_HOST
        domain, d_created = Domain.objects.get_or_create(
            domain=tenant_host,
            defaults={"tenant": tenant, "is_primary": True},
        )
        if d_created:
            self.stdout.write(self.style.SUCCESS(f"Created primary domain: {tenant_host}"))
        else:
            self.stdout.write(f"Domain already exists: {domain.domain}")

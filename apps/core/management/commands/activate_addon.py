"""Activate an addon for a tenant."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core.addons import registry
from apps.core.addons.events import dispatch_event
from apps.core.feature_flags import enable
from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Activate an addon for a tenant."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--addon", required=True)

    def handle(self, *args: Any, **opts: Any) -> None:
        try:
            tenant = Tenant.objects.get(schema_name=opts["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{opts['tenant']}' not found") from exc

        registry.discover()
        if registry.get(opts["addon"]) is None:
            raise CommandError(f"Addon '{opts['addon']}' not discovered")

        enable(tenant, opts["addon"])
        registry.call_lifecycle(opts["addon"], "on_activate", tenant)
        dispatch_event("addon_activated", {"tenant_schema": tenant.schema_name, "addon": opts["addon"]})
        self.stdout.write(self.style.SUCCESS(f"Activated {opts['addon']} for {tenant.schema_name}"))

"""Deactivate an addon for a tenant."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core.addons import registry
from apps.core.addons.events import dispatch_event
from apps.core.feature_flags import disable
from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Deactivate an addon for a tenant."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--addon", required=True)

    def handle(self, *args: Any, **opts: Any) -> None:
        try:
            tenant = Tenant.objects.get(schema_name=opts["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{opts['tenant']}' not found") from exc

        disable(tenant, opts["addon"])
        registry.call_lifecycle(opts["addon"], "on_deactivate", tenant)
        dispatch_event(
            "addon_deactivated", {"tenant_schema": tenant.schema_name, "addon": opts["addon"]}
        )
        self.stdout.write(self.style.SUCCESS(f"Deactivated {opts['addon']} for {tenant.schema_name}"))

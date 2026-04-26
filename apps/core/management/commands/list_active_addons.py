"""List active addons for a tenant."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import AddonActivation, Tenant


class Command(BaseCommand):
    help = "List active addons for a tenant."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True)

    def handle(self, *args: Any, **opts: Any) -> None:
        try:
            tenant = Tenant.objects.get(schema_name=opts["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{opts['tenant']}' not found") from exc

        activations = AddonActivation.objects.filter(tenant=tenant, active=True)
        if not activations:
            self.stdout.write(self.style.WARNING("No active addons."))
            return
        for a in activations:
            self.stdout.write(f"{a.addon_name:<30} activated {a.activated_at:%Y-%m-%d %H:%M}")

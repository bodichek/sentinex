"""One-shot helper to onboard a pilot tenant end-to-end.

Creates: Tenant + Domain + owner Invitation + weekly_brief activation.
Prints the invitation URL so the operator can paste it into the welcome email.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core.addons import registry
from apps.core.addons.events import dispatch_event
from apps.core.feature_flags import enable
from apps.core.models import Domain, Invitation, Role, Tenant


class Command(BaseCommand):
    help = "Provision a pilot tenant + owner invite + Weekly Brief activation."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--schema", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--domain", required=True)
        parser.add_argument("--owner-email", required=True)

    def handle(self, *args: Any, **opts: Any) -> None:
        schema = opts["schema"]
        if Tenant.objects.filter(schema_name=schema).exists():
            raise CommandError(f"Tenant '{schema}' already exists.")

        tenant = Tenant.objects.create(schema_name=schema, name=opts["name"])
        Domain.objects.create(domain=opts["domain"], tenant=tenant, is_primary=True)

        invitation = Invitation.objects.create(
            tenant=tenant, email=opts["owner_email"], role=Role.OWNER
        )

        enable(tenant, "weekly_brief")
        registry.call_lifecycle("weekly_brief", "on_activate", tenant)
        dispatch_event(
            "addon_activated",
            {"tenant_schema": tenant.schema_name, "addon": "weekly_brief"},
        )

        self.stdout.write(self.style.SUCCESS(f"Pilot tenant '{schema}' provisioned."))
        self.stdout.write(f"  Domain:         https://{opts['domain']}/")
        self.stdout.write(f"  Owner email:    {opts['owner_email']}")
        self.stdout.write(f"  Invitation URL: /invitations/{invitation.token}/")
        self.stdout.write("  Addon enabled:  weekly_brief")

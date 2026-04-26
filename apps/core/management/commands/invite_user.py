"""Create a tenant invitation from the CLI."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Invitation, Role, Tenant


class Command(BaseCommand):
    help = "Create an Invitation for an email to join a tenant with a role."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True, help="Tenant schema name")
        parser.add_argument("--email", required=True)
        parser.add_argument(
            "--role", default=Role.MEMBER.value, choices=[r.value for r in Role]
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        try:
            tenant = Tenant.objects.get(schema_name=opts["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{opts['tenant']}' not found.") from exc

        invitation = Invitation.objects.create(
            tenant=tenant, email=opts["email"], role=opts["role"]
        )
        self.stdout.write(self.style.SUCCESS("Invitation created."))
        self.stdout.write(f"  token: {invitation.token}")
        self.stdout.write(f"  accept URL: /invitations/{invitation.token}/")

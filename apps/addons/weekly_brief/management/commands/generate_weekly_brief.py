"""Manually trigger weekly brief generation for a tenant."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.addons.weekly_brief.services import WeeklyBriefGenerator
from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Generate a weekly brief for a tenant (uses current data)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", required=True, help="Tenant schema name")

    def handle(self, *args: Any, **opts: Any) -> None:
        try:
            tenant = Tenant.objects.get(schema_name=opts["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{opts['tenant']}' not found") from exc

        with schema_context(tenant.schema_name):
            report = WeeklyBriefGenerator().generate()

        self.stdout.write(self.style.SUCCESS(f"Generated report {report.uuid} ({report.status})"))

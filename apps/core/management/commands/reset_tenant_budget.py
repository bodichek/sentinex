"""Reset per-tenant monthly LLM budget spent counter."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Tenant, TenantBudget


class Command(BaseCommand):
    help = "Reset per-tenant monthly budget spent counter (run monthly via Celery Beat)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", help="Restrict to one tenant schema name")

    def handle(self, *args: Any, **opts: Any) -> None:
        qs = Tenant.objects.all()
        if opts["tenant"]:
            qs = qs.filter(schema_name=opts["tenant"])

        today = timezone.now().date().replace(day=1)
        n = 0
        for tenant in qs:
            budget, _ = TenantBudget.objects.get_or_create(tenant=tenant)
            budget.current_month_spent_czk = Decimal("0")
            budget.period_start = today
            budget.save(update_fields=["current_month_spent_czk", "period_start"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Reset budget for {n} tenant(s)."))

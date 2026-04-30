"""Celery tasks — Pipedrive sync per tenant."""

from __future__ import annotations

from celery import shared_task
from django_tenants.utils import schema_context

from apps.connectors.pipedrive.sync import run_sync


@shared_task(name="connectors.pipedrive.sync")  # type: ignore[untyped-decorator]
def sync_account(tenant_schema: str, days: int = 7) -> dict[str, int | str]:
    with schema_context(tenant_schema):
        snapshot = run_sync(days=days)
    return {
        "tenant_schema": tenant_schema,
        "snapshot_id": snapshot.pk if snapshot else 0,
    }


@shared_task(name="connectors.pipedrive.dispatch")  # type: ignore[untyped-decorator]
def dispatch() -> int:
    from apps.core.models import Tenant
    from apps.data_access.models import Integration

    schemas = list(
        Tenant.objects.filter(is_active=True)
        .exclude(schema_name="public")
        .values_list("schema_name", flat=True)
    )
    enabled: list[str] = []
    for schema in schemas:
        with schema_context(schema):
            if Integration.objects.filter(provider="pipedrive", is_active=True).exists():
                enabled.append(schema)
    for schema in enabled:
        sync_account.delay(schema)
    return len(enabled)

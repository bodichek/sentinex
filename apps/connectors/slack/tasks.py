"""Celery tasks — Slack workspace sync per tenant."""

from __future__ import annotations

from celery import shared_task
from django_tenants.utils import schema_context

from apps.connectors.slack.sync import run_sync


@shared_task(name="connectors.slack.sync_workspace")  # type: ignore[untyped-decorator]
def sync_workspace(tenant_schema: str, days: int = 7) -> dict[str, int | str]:
    with schema_context(tenant_schema):
        snapshot = run_sync(days=days)
    return {
        "tenant_schema": tenant_schema,
        "snapshot_id": snapshot.pk if snapshot else 0,
    }


@shared_task(name="connectors.slack.dispatch")  # type: ignore[untyped-decorator]
def dispatch() -> int:
    """Beat-driven fan-out across all tenants with active Slack integration."""
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
            if Integration.objects.filter(provider="slack", is_active=True).exists():
                enabled.append(schema)
    for schema in enabled:
        sync_workspace.delay(schema)
    return len(enabled)

"""Celery tasks for data sync pipelines."""

from __future__ import annotations

from celery import shared_task
from django_tenants.utils import schema_context

from apps.data_access.sync.google_workspace import run_sync
from apps.data_access.sync.slack import run_sync as run_slack_sync


@shared_task(name="data_access.sync_google_workspace_for_tenant")  # type: ignore[untyped-decorator]
def sync_google_workspace_for_tenant(tenant_schema: str, days: int = 7) -> dict[str, int | str]:
    with schema_context(tenant_schema):
        snapshot = run_sync(days=days)
    return {
        "tenant_schema": tenant_schema,
        "snapshot_id": snapshot.pk if snapshot else 0,
    }


@shared_task(name="data_access.sync_slack_workspace")  # type: ignore[untyped-decorator]
def sync_slack_workspace(tenant_schema: str, days: int = 7) -> dict[str, int | str]:
    """Sync Slack channels/messages/users for one tenant. Periodic via beat (6h)."""
    with schema_context(tenant_schema):
        snapshot = run_slack_sync(days=days)
    return {
        "tenant_schema": tenant_schema,
        "snapshot_id": snapshot.pk if snapshot else 0,
    }


@shared_task(name="data_access.sync_slack_dispatch")  # type: ignore[untyped-decorator]
def sync_slack_dispatch() -> int:
    """Beat-driven dispatcher: enqueue ``sync_slack_workspace`` for each active tenant."""
    from apps.core.models import Tenant

    schemas = list(
        Tenant.objects.filter(is_active=True)
        .exclude(schema_name="public")
        .values_list("schema_name", flat=True)
    )
    for schema in schemas:
        sync_slack_workspace.delay(schema)
    return len(schemas)

"""Celery tasks for data sync pipelines."""

from __future__ import annotations

from celery import shared_task
from django_tenants.utils import schema_context

from apps.data_access.sync.google_workspace import run_sync


@shared_task(name="data_access.sync_google_workspace_for_tenant")  # type: ignore[untyped-decorator]
def sync_google_workspace_for_tenant(tenant_schema: str, days: int = 7) -> dict[str, int | str]:
    with schema_context(tenant_schema):
        snapshot = run_sync(days=days)
    return {
        "tenant_schema": tenant_schema,
        "snapshot_id": snapshot.pk if snapshot else 0,
    }


# Slack sync tasks moved to ``apps.connectors.slack.tasks``.


# ---------------------------------------------------------------------------
# Workspace DWD tasks
# ---------------------------------------------------------------------------
@shared_task(name="data_access.sync_workspace_directory")  # type: ignore[untyped-decorator]
def sync_workspace_directory(tenant_schema: str, domain: str) -> dict[str, int | str]:
    from apps.data_access.sync.google_workspace_dwd import sync_directory_users

    with schema_context(tenant_schema):
        result = sync_directory_users(domain)
    return {"tenant_schema": tenant_schema, **result}


@shared_task(name="data_access.sync_workspace_audit")  # type: ignore[untyped-decorator]
def sync_workspace_audit(tenant_schema: str, days: int = 7) -> dict[str, int | str]:
    from apps.data_access.sync.google_workspace_dwd import sync_admin_audit_logins

    with schema_context(tenant_schema):
        result = sync_admin_audit_logins(days=days)
    return {"tenant_schema": tenant_schema, **result}


@shared_task(name="data_access.sync_workspace_user_calendar")  # type: ignore[untyped-decorator]
def sync_workspace_user_calendar(
    tenant_schema: str, user_email: str, days: int = 7
) -> dict[str, int | str]:
    from apps.data_access.sync.google_workspace_dwd import sync_user_calendar_week

    with schema_context(tenant_schema):
        result = sync_user_calendar_week(user_email, days=days)
    return {"tenant_schema": tenant_schema, **result}


@shared_task(name="data_access.knowledge_full_ingest")  # type: ignore[untyped-decorator]
def knowledge_full_ingest(tenant_schema: str) -> dict[str, int | str]:
    from apps.data_access.knowledge.tasks import full_ingest_workspace

    with schema_context(tenant_schema):
        result = full_ingest_workspace()
    return {"tenant_schema": tenant_schema, **result}


@shared_task(name="data_access.knowledge_incremental_ingest")  # type: ignore[untyped-decorator]
def knowledge_incremental_ingest(tenant_schema: str) -> dict[str, int | str]:
    from apps.data_access.knowledge.tasks import incremental_ingest_workspace

    with schema_context(tenant_schema):
        result = incremental_ingest_workspace()
    return {"tenant_schema": tenant_schema, **result}


# ---------------------------------------------------------------------------
# Beat dispatchers — fan a single beat tick out to every active tenant.
# Each guards itself against tenants that haven't enabled the DWD integration.
# ---------------------------------------------------------------------------
def _active_tenant_schemas() -> list[str]:
    from apps.core.models import Tenant

    return list(
        Tenant.objects.filter(is_active=True)
        .exclude(schema_name="public")
        .values_list("schema_name", flat=True)
    )


def _has_dwd_integration(schema: str) -> bool:
    from apps.data_access.models import Integration

    with schema_context(schema):
        return Integration.objects.filter(
            provider=Integration.PROVIDER_GOOGLE_WORKSPACE_DWD, is_active=True
        ).exists()


@shared_task(name="data_access.knowledge_incremental_dispatch")  # type: ignore[untyped-decorator]
def knowledge_incremental_dispatch() -> int:
    schemas = [s for s in _active_tenant_schemas() if _has_dwd_integration(s)]
    for schema in schemas:
        knowledge_incremental_ingest.delay(schema)
    return len(schemas)


@shared_task(name="data_access.workspace_directory_dispatch")  # type: ignore[untyped-decorator]
def workspace_directory_dispatch() -> int:
    from django.conf import settings

    domain = settings.GOOGLE_WORKSPACE_DOMAIN
    if not domain:
        return 0
    schemas = [s for s in _active_tenant_schemas() if _has_dwd_integration(s)]
    for schema in schemas:
        sync_workspace_directory.delay(schema, domain)
    return len(schemas)


@shared_task(name="data_access.workspace_audit_dispatch")  # type: ignore[untyped-decorator]
def workspace_audit_dispatch() -> int:
    schemas = [s for s in _active_tenant_schemas() if _has_dwd_integration(s)]
    for schema in schemas:
        sync_workspace_audit.delay(schema, 1)  # last 24 h
    return len(schemas)

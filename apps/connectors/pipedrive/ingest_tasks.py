"""Celery tasks driving Pipedrive ingest in dependency order:

    organizations → persons → deals → activities

Each step is a separate Celery task so partial failures don't poison the run.
A wrapper task runs them sequentially for a single Integration.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from apps.connectors._framework.base_sync import BaseSync
from apps.connectors._framework.models import SyncMode
from apps.connectors.pipedrive.ingest import (
    PipedriveActivitySync,
    PipedriveDealSync,
    PipedriveOrganizationSync,
    PipedrivePersonSync,
)
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "pipedrive"


def _resolve_integration(integration_id: int | None) -> Integration | None:
    if integration_id is not None:
        return Integration.objects.filter(id=integration_id).first()
    return Integration.objects.filter(provider=PROVIDER, is_active=True).first()


def _run(
    sync_cls: type[BaseSync], integration_id: int | None, mode: str
) -> dict[str, Any]:
    integration = _resolve_integration(integration_id)
    if integration is None:
        logger.warning("pipedrive integration not found (id=%s)", integration_id)
        return {"status": "skipped", "reason": "no_integration"}
    outcome = sync_cls(integration).run(mode=mode)
    return {
        "status": outcome.status,
        "fetched": outcome.fetched,
        "created": outcome.created,
        "updated": outcome.updated,
        "skipped": outcome.skipped,
        "errors": outcome.errors,
    }


@shared_task(name="pipedrive.ingest.organizations")
def ingest_organizations(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, Any]:
    return _run(PipedriveOrganizationSync, integration_id, mode)


@shared_task(name="pipedrive.ingest.persons")
def ingest_persons(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, Any]:
    return _run(PipedrivePersonSync, integration_id, mode)


@shared_task(name="pipedrive.ingest.deals")
def ingest_deals(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, Any]:
    return _run(PipedriveDealSync, integration_id, mode)


@shared_task(name="pipedrive.ingest.activities")
def ingest_activities(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, Any]:
    return _run(PipedriveActivitySync, integration_id, mode)


@shared_task(name="pipedrive.ingest.full")
def ingest_full(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, dict[str, Any]]:
    """Run all four ingest steps in order: orgs → persons → deals → activities."""
    return {
        "organizations": ingest_organizations(integration_id, mode),
        "persons": ingest_persons(integration_id, mode),
        "deals": ingest_deals(integration_id, mode),
        "activities": ingest_activities(integration_id, mode),
    }

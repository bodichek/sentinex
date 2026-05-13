"""Celery tasks driving FAPI ingest in order: customers -> invoices."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from apps.connectors._framework.base_sync import BaseSync
from apps.connectors._framework.models import SyncMode
from apps.connectors.fapi.ingest import FapiCustomerSync, FapiInvoiceSync
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)
PROVIDER = "fapi"


def _resolve_integration(integration_id: int | None) -> Integration | None:
    if integration_id is not None:
        return Integration.objects.filter(id=integration_id).first()
    return Integration.objects.filter(provider=PROVIDER, is_active=True).first()


def _run(
    sync_cls: type[BaseSync], integration_id: int | None, mode: str
) -> dict[str, Any]:
    integration = _resolve_integration(integration_id)
    if integration is None:
        return {"status": "skipped", "reason": "no_integration"}
    outcome = sync_cls(integration).run(mode=mode)
    return {
        "status": outcome.status, "fetched": outcome.fetched,
        "created": outcome.created, "updated": outcome.updated,
        "skipped": outcome.skipped, "errors": outcome.errors,
    }


@shared_task(name="fapi.ingest.customers")
def ingest_customers(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, Any]:
    return _run(FapiCustomerSync, integration_id, mode)


@shared_task(name="fapi.ingest.invoices")
def ingest_invoices(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, Any]:
    return _run(FapiInvoiceSync, integration_id, mode)


@shared_task(name="fapi.ingest.full")
def ingest_full(
    integration_id: int | None = None, mode: str = SyncMode.INCREMENTAL
) -> dict[str, dict[str, Any]]:
    return {
        "customers": ingest_customers(integration_id, mode),
        "invoices": ingest_invoices(integration_id, mode),
    }

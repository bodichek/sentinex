"""FAPI ingest — Customer + Invoice syncs.

Coexists with apps/connectors/fapi/sync.py (metric snapshots → DataSnapshot).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.connectors._framework.base_sync import BaseSync, SyncContext
from apps.connectors._framework.identity_hook import resolve_organization
from apps.connectors._framework.rate_limit import TokenBucket
from apps.connectors.fapi.client import FapiClient
from apps.connectors.fapi.models import (
    InvoiceStatus,
    ScbFapiCustomer,
    ScbFapiInvoice,
)

logger = logging.getLogger(__name__)

PROVIDER = "fapi"
RATE_LIMIT = TokenBucket("fapi", capacity=30, refill_per_sec=1.0)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return parse_datetime(str(value))


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return parse_date(str(value))


def _iter_paginated(call, page_size: int = 100) -> Iterator[dict[str, Any]]:
    """FAPI returns {data: [...], total: N} (typical convention); fall through
    to a list directly if returned as such."""
    offset = 0
    while True:
        resp = call(limit=page_size, offset=offset)
        if isinstance(resp, list):
            rows = resp
            for row in rows:
                yield row
            if len(rows) < page_size:
                return
        elif isinstance(resp, dict):
            rows = resp.get("data") or resp.get("invoices") or resp.get("clients") or []
            for row in rows:
                yield row
            if len(rows) < page_size:
                return
        else:
            return
        offset += page_size


class FapiCustomerSync(BaseSync):
    provider = PROVIDER
    resource = "customers"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with FapiClient(self.integration) as client:
            for row in _iter_paginated(client.list_clients):
                yield row

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        fapi_id = str(raw.get("id"))
        ico = (raw.get("ico") or raw.get("company_id") or "").strip()
        dic = (raw.get("dic") or raw.get("vat_id") or "").strip()
        email = (raw.get("email") or "").strip()
        name = (raw.get("name") or raw.get("company_name") or "").strip()

        master = resolve_organization(
            source_system=PROVIDER,
            name=name,
            ico=ico or None,
            dic=dic or None,
            id_in_source=fapi_id,
        )
        obj, created = ScbFapiCustomer.objects.update_or_create(
            fapi_id=fapi_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": fapi_id,
                "source_synced_at": timezone.now(),
                "source_updated_at": _parse_dt(raw.get("updated_at") or raw.get("update_time")),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "organization": master,
                "name": name[:255],
                "ico": ico,
                "dic": dic,
                "email": email,
                "phone": (raw.get("phone") or "")[:64],
                "address": raw.get("address") or {},
                "fapi_created_at": _parse_dt(raw.get("created_at") or raw.get("add_time")),
                "fapi_updated_at": _parse_dt(raw.get("updated_at") or raw.get("update_time")),
            },
        )
        return "created" if created else "updated"


def _map_invoice_status(value: Any) -> str:
    v = str(value or "").lower()
    if v in InvoiceStatus.values:
        return v
    mapping = {
        "issued": InvoiceStatus.SENT,
        "open": InvoiceStatus.SENT,
        "partially_paid": InvoiceStatus.PARTIAL,
        "fully_paid": InvoiceStatus.PAID,
        "canceled": InvoiceStatus.CANCELLED,
    }
    return mapping.get(v, InvoiceStatus.UNKNOWN)


class FapiInvoiceSync(BaseSync):
    provider = PROVIDER
    resource = "invoices"
    rate_limit = RATE_LIMIT

    def fetch(self, ctx: SyncContext) -> Iterator[dict[str, Any]]:
        with FapiClient(self.integration) as client:
            for row in _iter_paginated(client.list_invoices):
                yield row

    def persist(self, raw: dict[str, Any], ctx: SyncContext) -> str:
        fapi_id = str(raw.get("id"))
        client_id = raw.get("client_id") or raw.get("customer_id")
        customer_obj = None
        master_org = None
        if client_id is not None:
            customer_obj = ScbFapiCustomer.objects.filter(fapi_id=str(client_id)).first()
            if customer_obj:
                master_org = customer_obj.organization

        amount = Decimal(str(raw.get("price_with_vat") or raw.get("amount") or 0))
        vat_amount = Decimal(str(raw.get("vat") or raw.get("vat_amount") or 0))

        obj, created = ScbFapiInvoice.objects.update_or_create(
            fapi_id=fapi_id,
            defaults={
                "source_system": PROVIDER,
                "source_id": fapi_id,
                "source_synced_at": timezone.now(),
                "source_updated_at": _parse_dt(raw.get("updated_at") or raw.get("update_time")),
                "raw_payload": raw,
                "sync_run": ctx.run,
                "number": (raw.get("number") or raw.get("invoice_number") or "")[:64],
                "customer": customer_obj,
                "organization": master_org,
                "amount": amount,
                "vat_amount": vat_amount,
                "currency": (raw.get("currency") or "CZK")[:8],
                "status": _map_invoice_status(raw.get("status")),
                "issued_at": _parse_date(raw.get("issued_at") or raw.get("issue_date")),
                "due_at": _parse_date(raw.get("due_at") or raw.get("due_date")),
                "paid_at": _parse_date(raw.get("paid_at") or raw.get("paid_date")),
                "items": raw.get("items") or [],
                "fapi_created_at": _parse_dt(raw.get("created_at") or raw.get("add_time")),
                "fapi_updated_at": _parse_dt(raw.get("updated_at") or raw.get("update_time")),
            },
        )
        return "created" if created else "updated"

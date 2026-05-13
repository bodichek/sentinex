"""Merk enrichment service — on-demand lookup with cache and identity resolution.

Two entry points:

    enrich(ico)             — fetch + cache a single IČO, return ScbMerkCompany
    enrich_batch(icos)      — bulk lookup, up to 500 at a time

A cache hit older than ``REFRESH_AFTER_DAYS`` triggers a refresh; otherwise
the cached row is returned directly.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.connectors._framework.identity_hook import resolve_organization
from apps.connectors.merk.client import MerkClient
from apps.connectors.merk.models import ScbMerkCompany
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "merk"
REFRESH_AFTER_DAYS = 30


def _resolve_integration() -> Integration | None:
    return Integration.objects.filter(provider=PROVIDER, is_active=True).first()


def _cache_fresh(row: ScbMerkCompany) -> bool:
    if not row.source_synced_at:
        return False
    return bool(timezone.now() - row.source_synced_at < timedelta(days=REFRESH_AFTER_DAYS))


def _upsert(ico: str, payload: dict[str, Any]) -> ScbMerkCompany:
    name = (payload.get("name") or payload.get("subject_name") or "").strip()
    dic = (payload.get("dic") or payload.get("vat_id") or "").strip()
    org = resolve_organization(
        source_system=PROVIDER, name=name or ico, ico=ico, dic=dic or None,
        id_in_source=ico,
    )
    row, _ = ScbMerkCompany.objects.update_or_create(
        ico=ico,
        defaults={
            "source_system": PROVIDER,
            "source_id": ico,
            "source_synced_at": timezone.now(),
            "raw_payload": payload,
            "organization": org,
            "dic": dic,
            "name": name[:255],
            "legal_form": (payload.get("legal_form") or "")[:64],
            "status": (payload.get("status") or "")[:32],
            "nace_codes": payload.get("nace") or payload.get("nace_codes") or [],
            "employee_count_range": (payload.get("employee_count_range") or "")[:32],
            "turnover_range": (payload.get("turnover_range") or "")[:32],
            "last_known_turnover": payload.get("turnover_last"),
            "turnover_year": payload.get("turnover_year"),
            "profit_last": payload.get("profit_last"),
            "profit_year": payload.get("profit_year"),
            "rating": (payload.get("rating") or "")[:16],
            "rating_breakdown": payload.get("rating_breakdown") or {},
            "address": payload.get("address") or {},
            "website": (payload.get("website") or "")[:255],
            "contacts_summary": payload.get("contacts") or {},
        },
    )
    return row


def enrich(ico: str, *, force_refresh: bool = False) -> ScbMerkCompany | None:
    """Lookup a single IČO. Returns cached row when fresh enough."""
    if not ico:
        return None
    existing = ScbMerkCompany.objects.filter(ico=ico).first()
    if existing and not force_refresh and _cache_fresh(existing):
        return existing

    integration = _resolve_integration()
    if integration is None:
        logger.warning("merk integration not configured; returning cached row if any")
        return existing

    with MerkClient(integration) as client:
        payload = client.lookup_by_ico(ico)
    return _upsert(ico, payload)


def enrich_batch(icos: list[str], *, force_refresh: bool = False) -> list[ScbMerkCompany]:
    """Bulk lookup. Splits internally into 500-item batches per Merk API limit."""
    icos = [i for i in (str(x).strip() for x in icos) if i]
    if not icos:
        return []
    integration = _resolve_integration()
    if integration is None:
        return list(ScbMerkCompany.objects.filter(ico__in=icos))

    to_fetch: list[str] = []
    cached_rows: dict[str, ScbMerkCompany] = {
        row.ico: row for row in ScbMerkCompany.objects.filter(ico__in=icos)
    }
    for ico in icos:
        row = cached_rows.get(ico)
        if not row or force_refresh or not _cache_fresh(row):
            to_fetch.append(ico)

    results: list[ScbMerkCompany] = []
    with MerkClient(integration) as client:
        for i in range(0, len(to_fetch), 500):
            chunk = to_fetch[i : i + 500]
            payloads = client.batch_lookup(chunk)
            for payload in payloads:
                ico = str(payload.get("ico") or payload.get("subject_id") or "")
                if not ico:
                    continue
                results.append(_upsert(ico, payload))

    for ico in icos:
        if ico in cached_rows and ico not in {r.ico for r in results}:
            results.append(cached_rows[ico])
    return results

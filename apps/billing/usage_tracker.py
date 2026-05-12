"""Usage tracker that reads from ClickHouse and caches in Redis."""

from __future__ import annotations

import asyncio
import json
from datetime import date

from django.core.cache import cache

from apps.analytics.clickhouse_client import SentinexClickHouseClient
from apps.analytics.schemas import TenantUsageSummary

CACHE_TTL_SECONDS = 60 * 60  # 1h


def _cache_key(tenant_id: str, f: date, t: date) -> str:
    return f"billing:usage:{tenant_id}:{f.isoformat()}:{t.isoformat()}"


def get_usage(
    tenant_id: str,
    from_date: date,
    to_date: date,
    *,
    client: SentinexClickHouseClient | None = None,
    use_cache: bool = True,
) -> TenantUsageSummary:
    """Return cached or freshly-computed usage summary for the period."""
    key = _cache_key(tenant_id, from_date, to_date)
    if use_cache:
        cached = cache.get(key)
        if cached:
            return TenantUsageSummary.model_validate(json.loads(cached))

    ch = client or SentinexClickHouseClient()
    summary: TenantUsageSummary = asyncio.run(
        ch.get_tenant_usage(tenant_id, from_date, to_date)
    )
    if use_cache:
        cache.set(key, summary.model_dump_json(), CACHE_TTL_SECONDS)
    return summary

"""Tenant feature flags backed by AddonActivation, cached in Redis."""

from __future__ import annotations

from django.core.cache import cache

from apps.core.models import AddonActivation, Tenant

CACHE_TTL = 5 * 60


def _key(tenant: Tenant, feature: str) -> str:
    return f"ff:{tenant.pk}:{feature}"


def is_enabled(tenant: Tenant, feature_name: str) -> bool:
    key = _key(tenant, feature_name)
    cached = cache.get(key)
    if cached is not None:
        return bool(cached)
    active = AddonActivation.objects.filter(
        tenant=tenant, addon_name=feature_name, active=True
    ).exists()
    cache.set(key, active, CACHE_TTL)
    return active


def enable(tenant: Tenant, feature_name: str) -> AddonActivation:
    activation, _ = AddonActivation.objects.update_or_create(
        tenant=tenant, addon_name=feature_name, defaults={"active": True, "deactivated_at": None}
    )
    cache.delete(_key(tenant, feature_name))
    return activation


def disable(tenant: Tenant, feature_name: str) -> None:
    from django.utils import timezone

    AddonActivation.objects.filter(tenant=tenant, addon_name=feature_name).update(
        active=False, deactivated_at=timezone.now()
    )
    cache.delete(_key(tenant, feature_name))

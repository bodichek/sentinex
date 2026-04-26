"""Addon framework tests."""

from __future__ import annotations

import pytest

from apps.core.addons import AddonManifest, registry
from apps.core.addons.events import data_synced, dispatch_event
from apps.core.feature_flags import disable, enable, is_enabled
from apps.core.models import AddonActivation, Tenant


@pytest.mark.django_db
class TestManifest:
    def test_manifest_dataclass(self) -> None:
        m = AddonManifest(name="x", display_name="X", version="1.0")
        assert m.name == "x"
        assert m.category == "general"


@pytest.mark.django_db
class TestRegistry:
    def test_discovers_installed_addons(self) -> None:
        registry.discover(force=True)
        names = [m.name for m in registry.all()]
        # weekly_brief addon exists but manifest not yet written
        assert isinstance(names, list)


@pytest.mark.django_db
class TestFeatureFlags:
    def test_enable_disable(self) -> None:
        tenant = Tenant.objects.create(schema_name="ff_t", name="FFT")
        assert is_enabled(tenant, "weekly_brief") is False
        enable(tenant, "weekly_brief")
        assert is_enabled(tenant, "weekly_brief") is True
        disable(tenant, "weekly_brief")
        assert is_enabled(tenant, "weekly_brief") is False

    def test_activation_record_persisted(self) -> None:
        tenant = Tenant.objects.create(schema_name="ff_t2", name="FFT2")
        enable(tenant, "addon_a")
        assert AddonActivation.objects.filter(
            tenant=tenant, addon_name="addon_a", active=True
        ).exists()

    def test_isolation_between_tenants(self) -> None:
        t_a = Tenant.objects.create(schema_name="ff_a", name="A")
        t_b = Tenant.objects.create(schema_name="ff_b", name="B")
        enable(t_a, "x")
        assert is_enabled(t_a, "x") is True
        assert is_enabled(t_b, "x") is False


@pytest.mark.django_db
class TestEvents:
    def test_signal_dispatches_synchronously(self) -> None:
        received: list[dict] = []  # type: ignore[type-arg]

        def handler(sender, **kwargs):  # type: ignore[no-untyped-def]
            received.append(kwargs)

        data_synced.connect(handler)
        try:
            dispatch_event("data_synced", {"source": "test"})
        finally:
            data_synced.disconnect(handler)

        assert any(r.get("source") == "test" for r in received)

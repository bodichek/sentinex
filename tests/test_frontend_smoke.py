"""Frontend smoke tests: dashboard, weekly brief list, insights — 200 OK on tenant subdomain."""

from __future__ import annotations

import uuid

import pytest
from django.test import Client

from apps.core.models import AddonActivation, Domain, Role, Tenant, TenantMembership, User


@pytest.fixture
def tenant_client() -> tuple[Client, Tenant, User]:
    tenant, _ = Tenant.objects.get_or_create(
        schema_name="test_tenant", defaults={"name": "Test"}
    )
    Domain.objects.get_or_create(
        domain="test.sentinex.local",
        defaults={"tenant": tenant, "is_primary": True},
    )
    user = User.objects.create_user(
        email=f"frontend-{uuid.uuid4().hex[:8]}@example.com", password="pw-12345678"
    )
    TenantMembership.objects.create(user=user, tenant=tenant, role=Role.OWNER)
    AddonActivation.objects.update_or_create(
        tenant=tenant, addon_name="weekly_brief", defaults={"active": True}
    )
    client = Client(HTTP_HOST="test.sentinex.local")
    client.force_login(user)
    return client, tenant, user


@pytest.mark.django_db(transaction=True)
class TestFrontendSmoke:
    def test_dashboard_returns_200(self, tenant_client: tuple[Client, Tenant, User]) -> None:
        client, _, _ = tenant_client
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.content

    def test_weekly_brief_history_returns_200(
        self, tenant_client: tuple[Client, Tenant, User]
    ) -> None:
        client, _, _ = tenant_client
        resp = client.get("/addons/weekly-brief/history/")
        assert resp.status_code == 200
        assert b"Weekly Brief" in resp.content

    def test_insights_index_returns_200(
        self, tenant_client: tuple[Client, Tenant, User]
    ) -> None:
        client, _, _ = tenant_client
        resp = client.get("/insights/")
        assert resp.status_code == 200
        assert b"Insights" in resp.content

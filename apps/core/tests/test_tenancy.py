"""Tenancy tests: tenant creation, schema switching, data isolation."""

from __future__ import annotations

import pytest
from django.db import connection
from django_tenants.utils import schema_context

from apps.core.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
class TestTenantCreation:
    def test_create_tenant_creates_schema(self) -> None:
        tenant = Tenant.objects.create(schema_name="acme_test", name="ACME Test")
        Domain.objects.create(
            domain="acme-test.sentinex.local", tenant=tenant, is_primary=True
        )

        assert Tenant.objects.filter(schema_name="acme_test").exists()
        with connection.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                ["acme_test"],
            )
            assert cur.fetchone() is not None

    def test_primary_domain_resolves_to_tenant(self) -> None:
        tenant = Tenant.objects.create(schema_name="resolve_test", name="Resolve Test")
        Domain.objects.create(
            domain="resolve.sentinex.local", tenant=tenant, is_primary=True
        )
        fetched = Domain.objects.get(domain="resolve.sentinex.local").tenant
        assert fetched.pk == tenant.pk


@pytest.mark.django_db(transaction=True)
class TestTenantIsolation:
    def test_schema_context_switches_connection(self) -> None:
        tenant_a = Tenant.objects.create(schema_name="iso_a", name="A")
        tenant_b = Tenant.objects.create(schema_name="iso_b", name="B")

        with schema_context(tenant_a.schema_name):
            assert connection.schema_name == "iso_a"  # type: ignore[attr-defined]
        with schema_context(tenant_b.schema_name):
            assert connection.schema_name == "iso_b"  # type: ignore[attr-defined]

    def test_tables_isolated_between_schemas(self) -> None:
        tenant_a = Tenant.objects.create(schema_name="data_a", name="DA")
        tenant_b = Tenant.objects.create(schema_name="data_b", name="DB")

        with schema_context(tenant_a.schema_name), connection.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS isolation_probe (v int)")
            cur.execute("INSERT INTO isolation_probe VALUES (1)")

        with schema_context(tenant_b.schema_name), connection.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('isolation_probe')",
            )
            result = cur.fetchone()
            assert result is not None
            assert result[0] is None, (
                f"Table from schema {tenant_a.schema_name} leaked into "
                f"{tenant_b.schema_name}: {result[0]}"
            )

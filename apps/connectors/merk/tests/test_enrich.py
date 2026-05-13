from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.merk.models import ScbMerkCompany
from apps.connectors.merk.services import enrich
from apps.data_access.models import Credential, Integration
from apps.identity.models import Organization


@contextmanager
def _tenant():
    with schema_context("test_tenant"):
        yield


@pytest.fixture
def integration(db) -> Integration:
    with _tenant():
        integ = Integration.objects.create(provider="merk", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"api_key": "merk-fake-key"})
        cred.save()
    return integ


@pytest.mark.django_db
def test_enrich_creates_cache_row_and_master_organization(integration: Integration) -> None:
    fake_payload = {
        "ico": "12345678",
        "name": "ACME s.r.o.",
        "dic": "CZ12345678",
        "legal_form": "s.r.o.",
        "status": "active",
        "nace": ["62010"],
        "employee_count_range": "10-49",
        "turnover_range": "10-50M",
        "rating": "B",
        "address": {"city": "Praha", "country": "CZ"},
    }
    with _tenant(), patch("apps.connectors.merk.services.MerkClient") as MockClient:
        ctx = MockClient.return_value.__enter__.return_value
        ctx.lookup_by_ico.return_value = fake_payload
        row = enrich("12345678")

    assert row is not None
    with _tenant():
        cached = ScbMerkCompany.objects.get(ico="12345678")
        assert cached.name == "ACME s.r.o."
        assert cached.rating == "B"
        assert cached.organization_id is not None
        org_id = cached.organization_id
    assert Organization.objects.filter(id=org_id, ico="12345678").exists()


@pytest.mark.django_db
def test_enrich_uses_cache_when_fresh(integration: Integration) -> None:
    with _tenant(), patch("apps.connectors.merk.services.MerkClient") as MockClient:
        MockClient.return_value.__enter__.return_value.lookup_by_ico.return_value = {
            "ico": "12345678", "name": "ACME", "dic": "CZ12345678"
        }
        enrich("12345678")

    # second call must not hit the network
    with _tenant(), patch("apps.connectors.merk.services.MerkClient") as MockClient:
        result = enrich("12345678")
        MockClient.assert_not_called()
    assert result is not None
    assert result.ico == "12345678"

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors._framework.models import SyncStatus
from apps.connectors.fapi.ingest import FapiCustomerSync, FapiInvoiceSync
from apps.connectors.fapi.models import ScbFapiCustomer, ScbFapiInvoice
from apps.data_access.models import Credential, Integration
from apps.identity.models import Organization


@contextmanager
def _tenant():
    with schema_context("test_tenant"):
        yield


@pytest.fixture
def integration(db) -> Integration:
    with _tenant():
        integ = Integration.objects.create(provider="fapi", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"username": "test", "api_key": "test"})
        cred.save()
    return integ


@pytest.mark.django_db
def test_customer_sync_resolves_organization_by_ico(integration: Integration) -> None:
    sample = {
        "data": [
            {"id": 1, "name": "ACME s.r.o.", "ico": "12345678", "dic": "CZ12345678",
             "email": "fakturace@acme.cz", "phone": "+420111222333",
             "address": {"city": "Praha"},
             "created_at": "2026-01-15T10:00:00Z",
             "updated_at": "2026-04-01T12:00:00Z"},
        ]
    }
    with _tenant(), patch("apps.connectors.fapi.ingest.FapiClient") as MockClient:
        MockClient.return_value.__enter__.return_value.list_clients.return_value = sample
        outcome = FapiCustomerSync(integration).run()
    assert outcome.status == SyncStatus.COMPLETED
    assert outcome.created == 1
    with _tenant():
        mirror = ScbFapiCustomer.objects.get(fapi_id="1")
        assert mirror.ico == "12345678"
        assert mirror.organization_id is not None
        master_id = mirror.organization_id
    assert Organization.objects.filter(id=master_id, ico="12345678").exists()


@pytest.mark.django_db
def test_invoice_sync_links_to_customer_and_organization(integration: Integration) -> None:
    with _tenant(), patch("apps.connectors.fapi.ingest.FapiClient") as MockClient:
        MockClient.return_value.__enter__.return_value.list_clients.return_value = {
            "data": [{"id": 1, "name": "ACME", "ico": "12345678", "email": "a@b.cz"}]
        }
        FapiCustomerSync(integration).run()

    invoices = {
        "data": [
            {"id": 42, "number": "2026/0042", "client_id": 1,
             "price_with_vat": "12100.00", "vat": "2100.00",
             "currency": "CZK", "status": "paid",
             "issued_at": "2026-03-01", "due_at": "2026-03-15", "paid_at": "2026-03-10",
             "items": [{"name": "Founder kurz", "qty": 1, "price": 10000}]},
        ]
    }
    with _tenant(), patch("apps.connectors.fapi.ingest.FapiClient") as MockClient:
        MockClient.return_value.__enter__.return_value.list_invoices.return_value = invoices
        outcome = FapiInvoiceSync(integration).run()

    assert outcome.status == SyncStatus.COMPLETED
    with _tenant():
        inv = ScbFapiInvoice.objects.get(fapi_id="42")
        assert inv.number == "2026/0042"
        assert inv.status == "paid"
        assert inv.customer_id is not None
        assert inv.organization_id is not None
        assert str(inv.amount) == "12100.00"

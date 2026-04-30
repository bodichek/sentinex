from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.fapi.integration import FapiIntegration
from apps.connectors.fapi.sync import _summarise_invoices
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert FapiIntegration.provider == "fapi"


def test_summarise_invoices() -> None:
    invs = [
        {"paid_status": "paid", "price_total_with_vat": 12100},
        {"paid_status": "open", "price_total_with_vat": 5000},
        {"paid_status": "Paid", "price_total_with_vat": 9900},
    ]
    s = _summarise_invoices(invs)
    assert s["count"] == 3
    assert s["paid_with_vat"] == 22000.0
    assert s["total_with_vat"] == 27000.0


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="fapi").delete()
        integ = Integration.objects.create(provider="fapi", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"user": "ucet@firma.cz", "api_key": "K"})
        cred.save()
        fake = MagicMock()
        fake.list_invoices.return_value = {"items": [{"paid_status": "open"}]}
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch("apps.connectors.fapi.integration.FapiClient", return_value=fake):
            r = FapiIntegration().call(integ, "invoices.list", {"limit": 10})
        assert r.ok

"""Raynet integration unit tests (no real network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django_tenants.utils import schema_context

from apps.connectors.raynet.integration import RaynetIntegration
from apps.connectors.raynet.sync import _summarise_business_cases
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert RaynetIntegration.provider == "raynet"


def test_exchange_code_parses_triple() -> None:
    spec = RaynetIntegration().exchange_code("acme:user@x.cz:KEY", "")
    assert spec == {"instance": "acme", "username": "user@x.cz", "api_key": "KEY"}


def test_exchange_code_rejects_partial() -> None:
    with pytest.raises(ValueError):
        RaynetIntegration().exchange_code("acme:onlyuser", "")


def test_summarise_business_cases() -> None:
    items = [
        {"state": "OPEN", "priceMain": 100},
        {"state": "WON", "priceMain": 250},
        {"state": "OPEN", "priceMain": 50},
        {"state": "LOST", "priceMain": 30},
    ]
    s = _summarise_business_cases(items)
    assert s["total"] == 4
    assert s["open"] == 2
    assert s["won_value"] == 250.0
    assert s["total_value"] == 430.0


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="raynet").delete()
        integ = Integration.objects.create(provider="raynet", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"instance": "acme", "username": "u", "api_key": "k"})
        cred.save()

        fake = MagicMock()
        fake.list_companies.return_value = {"totalCount": 5, "data": []}
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch("apps.connectors.raynet.integration.RaynetClient", return_value=fake):
            r = RaynetIntegration().call(integ, "companies.list", {"limit": 1})
        assert r.ok and r.data["totalCount"] == 5

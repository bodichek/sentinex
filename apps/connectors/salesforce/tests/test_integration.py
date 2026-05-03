"""Salesforce smoke tests — mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.salesforce import oauth
from apps.connectors.salesforce.integration import SalesforceIntegration
from apps.connectors.salesforce.sync import _summarise_opps
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert SalesforceIntegration.provider == "salesforce"


@override_settings(SALESFORCE_CLIENT_ID="cid", SALESFORCE_CLIENT_SECRET="csec")
def test_authorization_url_carries_state() -> None:
    url = oauth.authorization_url("STATE", "https://app/cb")
    assert "client_id=cid" in url and "state=STATE" in url and "scope=api" in url


def test_summarise_opps_counts_by_status_and_stage() -> None:
    opps = [
        {"StageName": "Prospecting", "Amount": 100, "IsClosed": False, "IsWon": False},
        {"StageName": "Closed Won", "Amount": 500, "IsClosed": True, "IsWon": True},
        {"StageName": "Closed Lost", "Amount": 50, "IsClosed": True, "IsWon": False},
    ]
    s = _summarise_opps(opps)
    assert s["total"] == 3
    assert s["open"] == 1
    assert s["by_status"] == {"open": 1, "won": 1, "lost": 1}
    assert s["won_amount"] == 500.0
    assert s["total_amount"] == 650.0
    assert "Closed Won" in s["by_stage"]


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="salesforce").delete()
        integ = Integration.objects.create(provider="salesforce", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens(
            {
                "access_token": "AT",
                "refresh_token": "RT",
                "instance_url": "https://acme.my.salesforce.com",
            }
        )
        cred.save()
        fake = MagicMock()
        fake.list_accounts.return_value = {"totalSize": 12, "records": []}
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch(
            "apps.connectors.salesforce.integration.SalesforceClient",
            return_value=fake,
        ):
            r = SalesforceIntegration().call(integ, "accounts.list", {"limit": 1})
        assert r.ok and r.data["totalSize"] == 12

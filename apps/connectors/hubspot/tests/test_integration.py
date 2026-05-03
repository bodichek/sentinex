"""HubSpot smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.hubspot import oauth
from apps.connectors.hubspot.integration import HubspotIntegration
from apps.connectors.hubspot.sync import _summarise_deals
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert HubspotIntegration.provider == "hubspot"


@override_settings(HUBSPOT_CLIENT_ID="cid", HUBSPOT_CLIENT_SECRET="csec")
def test_authorization_url_includes_scopes() -> None:
    url = oauth.authorization_url("S", "https://app/cb")
    assert "client_id=cid" in url
    assert "crm.objects.deals.read" in url


def test_summarise_deals_uses_hs_is_closed_flags() -> None:
    deals = [
        {"properties": {"dealstage": "qualified", "amount": "100", "hs_is_closed": "false"}},
        {"properties": {"dealstage": "closedwon", "amount": "300", "hs_is_closed": "true", "hs_is_closed_won": "true"}},
        {"properties": {"dealstage": "closedlost", "amount": "50", "hs_is_closed": "true"}},
    ]
    s = _summarise_deals(deals)
    assert s["total"] == 3
    assert s["by_status"] == {"open": 1, "won": 1, "lost": 1}
    assert s["won_amount"] == 300.0
    assert s["total_amount"] == 450.0


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="hubspot").delete()
        integ = Integration.objects.create(provider="hubspot", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"access_token": "AT", "refresh_token": "RT"})
        cred.save()
        fake = MagicMock()
        fake.list_pipelines.return_value = [{"id": "default", "label": "Sales"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch(
            "apps.connectors.hubspot.integration.HubspotClient", return_value=fake
        ):
            r = HubspotIntegration().call(integ, "pipelines.list", {})
        assert r.ok and r.data[0]["label"] == "Sales"

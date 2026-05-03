"""Mailchimp smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.mailchimp import oauth
from apps.connectors.mailchimp.integration import MailchimpIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert MailchimpIntegration.provider == "mailchimp"


@override_settings(MAILCHIMP_CLIENT_ID="cid", MAILCHIMP_CLIENT_SECRET="csec")
def test_exchange_code_fetches_metadata() -> None:
    token = MagicMock()
    token.json.return_value = {"access_token": "AT", "scope": ""}
    token.raise_for_status.return_value = None
    meta = MagicMock()
    meta.json.return_value = {"dc": "us20", "api_endpoint": "https://us20.api.mailchimp.com", "login_url": "https://login.mailchimp.com"}
    meta.raise_for_status.return_value = None
    with patch("apps.connectors.mailchimp.oauth.httpx.post", return_value=token), patch(
        "apps.connectors.mailchimp.oauth.httpx.get", return_value=meta
    ):
        tokens = oauth.exchange_code("CODE", "https://app/cb")
    assert tokens["dc"] == "us20"
    assert tokens["api_endpoint"].startswith("https://us20")


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="mailchimp").delete()
        integ = Integration.objects.create(provider="mailchimp", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens(
            {"access_token": "AT", "dc": "us1", "api_endpoint": "https://us1.api.mailchimp.com"}
        )
        cred.save()
        fake = MagicMock()
        fake.list_audiences.return_value = [{"id": "a1", "name": "All", "stats": {"member_count": 10}}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch(
            "apps.connectors.mailchimp.integration.MailchimpClient", return_value=fake
        ):
            r = MailchimpIntegration().call(integ, "audiences.list", {})
        assert r.ok and r.data[0]["stats"]["member_count"] == 10

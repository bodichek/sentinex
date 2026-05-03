"""Basecamp smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.basecamp import oauth
from apps.connectors.basecamp.integration import BasecampIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert BasecampIntegration.provider == "basecamp"


@override_settings(BASECAMP_CLIENT_ID="cid", BASECAMP_CLIENT_SECRET="csec")
def test_authorization_url_uses_web_server_flow() -> None:
    url = oauth.authorization_url("S", "https://app/cb")
    assert "type=web_server" in url and "client_id=cid" in url


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="basecamp").delete()
        integ = Integration.objects.create(provider="basecamp", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens(
            {"access_token": "AT", "refresh_token": "RT", "account_id": 42}
        )
        cred.save()
        fake = MagicMock()
        fake.list_projects.return_value = [{"id": 1, "name": "Onboarding", "status": "active"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch(
            "apps.connectors.basecamp.integration.BasecampClient", return_value=fake
        ):
            r = BasecampIntegration().call(integ, "projects.list", {})
        assert r.ok and r.data[0]["status"] == "active"

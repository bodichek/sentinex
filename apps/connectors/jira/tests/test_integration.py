"""Jira (Atlassian) smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.jira import oauth
from apps.connectors.jira.integration import JiraIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert JiraIntegration.provider == "jira"


@override_settings(ATLASSIAN_CLIENT_ID="cid", ATLASSIAN_CLIENT_SECRET="csec")
def test_authorization_url_uses_atlassian_audience() -> None:
    url = oauth.authorization_url("S", "https://app/cb")
    assert "audience=api.atlassian.com" in url
    assert "read%3Ajira-work" in url
    assert "prompt=consent" in url


@override_settings(ATLASSIAN_CLIENT_ID="cid", ATLASSIAN_CLIENT_SECRET="csec")
def test_exchange_code_resolves_cloud_id() -> None:
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}
    token_resp.raise_for_status.return_value = None
    res_resp = MagicMock()
    res_resp.json.return_value = [{"id": "abc", "url": "https://acme.atlassian.net", "name": "Acme"}]
    res_resp.raise_for_status.return_value = None
    with patch(
        "apps.connectors.jira.oauth.httpx.post", return_value=token_resp
    ), patch("apps.connectors.jira.oauth.httpx.get", return_value=res_resp):
        tokens = oauth.exchange_code("CODE", "https://app/cb")
    assert tokens["access_token"] == "AT"
    assert tokens["cloud_id"] == "abc"


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="jira").delete()
        integ = Integration.objects.create(provider="jira", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"access_token": "AT", "refresh_token": "RT", "cloud_id": "abc"})
        cred.save()
        fake = MagicMock()
        fake.list_projects.return_value = [{"id": "1", "key": "OPS", "name": "Ops"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None
        with patch("apps.connectors.jira.integration.JiraClient", return_value=fake):
            r = JiraIntegration().call(integ, "projects.list", {})
        assert r.ok and r.data[0]["key"] == "OPS"

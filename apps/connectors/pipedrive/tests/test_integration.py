"""Pipedrive integration tests — mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.pipedrive.integration import PipedriveIntegration, refresh_tokens
from apps.connectors.pipedrive.sync import _summarise_deals
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert PipedriveIntegration.provider == "pipedrive"


@override_settings(PIPEDRIVE_CLIENT_ID="cid", PIPEDRIVE_CLIENT_SECRET="csec")
def test_authorization_url_contains_client_id_and_state() -> None:
    url = PipedriveIntegration().authorization_url("STATE", "https://app/cb")
    assert "client_id=cid" in url
    assert "state=STATE" in url
    assert "redirect_uri=https" in url


@override_settings(PIPEDRIVE_CLIENT_ID="cid", PIPEDRIVE_CLIENT_SECRET="csec")
def test_refresh_tokens_calls_token_url() -> None:
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "access_token": "AT2",
        "refresh_token": "RT2",
        "expires_in": 3600,
        "api_domain": "https://api-acme.pipedrive.com",
        "scope": "deals:read",
    }
    fake_resp.raise_for_status.return_value = None
    with patch("apps.connectors.pipedrive.integration.httpx.post", return_value=fake_resp):
        new = refresh_tokens({"refresh_token": "RT1"})
    assert new["access_token"] == "AT2"
    assert new["api_domain"] == "https://api-acme.pipedrive.com"


def test_summarise_deals_buckets_by_status_and_stage() -> None:
    deals = [
        {"status": "open", "stage_id": 1, "value": 100},
        {"status": "won", "stage_id": 2, "value": 250},
        {"status": "lost", "stage_id": 1, "value": 50},
        {"status": "open", "stage_id": 1, "value": 75},
    ]
    s = _summarise_deals(deals)
    assert s["total"] == 4
    assert s["open"] == 2
    assert s["by_status"] == {"open": 2, "won": 1, "lost": 1}
    assert s["total_value"] == 475.0
    assert s["won_value"] == 250.0
    assert s["by_stage"]["1"]["count"] == 3


@pytest.mark.django_db(transaction=True)
def test_call_dispatches_to_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="pipedrive").delete()
        integ = Integration.objects.create(provider="pipedrive", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens(
            {
                "access_token": "AT",
                "refresh_token": "RT",
                "api_domain": "https://api.pipedrive.com",
            }
        )
        cred.save()

        fake = MagicMock()
        fake.list_pipelines.return_value = [{"id": 1, "name": "Default"}]
        fake.__enter__.return_value = fake
        fake.__exit__.return_value = None

        with patch(
            "apps.connectors.pipedrive.integration.PipedriveClient", return_value=fake
        ):
            result = PipedriveIntegration().call(integ, "pipelines.list", {})
        assert result.ok
        assert result.data == [{"id": 1, "name": "Default"}]

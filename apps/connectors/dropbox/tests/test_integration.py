"""Dropbox (MCP + PKCE) smoke tests."""

from __future__ import annotations

import base64
import hashlib
from unittest.mock import patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.dropbox import oauth
from apps.connectors.dropbox.client import ToolResult
from apps.connectors.dropbox.integration import DropboxIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert DropboxIntegration.provider == "dropbox"


def test_pkce_pair_uses_s256() -> None:
    verifier, challenge = oauth.generate_pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    assert challenge == expected


@override_settings(DROPBOX_CLIENT_ID="cid", DROPBOX_CLIENT_SECRET="csec")
def test_authorization_url_includes_pkce_and_offline() -> None:
    url = oauth.authorization_url("S", "https://app/cb", "CHALLENGE")
    assert "code_challenge=CHALLENGE" in url
    assert "code_challenge_method=S256" in url
    assert "token_access_type=offline" in url


@pytest.mark.django_db(transaction=True)
def test_call_proxies_to_mcp_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="dropbox").delete()
        integ = Integration.objects.create(provider="dropbox", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"access_token": "AT", "refresh_token": "RT"})
        cred.save()
        result = ToolResult(is_error=False, text_blocks=['{"entries": [1, 2, 3]}'])
        with patch(
            "apps.connectors.dropbox.integration.dropbox_client.call_tool",
            return_value=result,
        ) as called:
            r = DropboxIntegration().call(integ, "files/list_folder", {"path": ""})
        called.assert_called_once_with("AT", "files/list_folder", {"path": ""})
        assert r.ok and r.data == {"entries": [1, 2, 3]}

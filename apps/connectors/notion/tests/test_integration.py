"""Notion (MCP) smoke tests — no real network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django_tenants.utils import schema_context

from apps.connectors.notion import oauth
from apps.connectors.notion.client import ToolResult
from apps.connectors.notion.integration import NotionIntegration
from apps.data_access.models import Credential, Integration


def test_provider_advertised() -> None:
    assert NotionIntegration.provider == "notion"


@override_settings(NOTION_CLIENT_ID="cid", NOTION_CLIENT_SECRET="csec")
def test_authorization_url_uses_owner_user() -> None:
    url = oauth.authorization_url("S", "https://app/cb")
    assert "client_id=cid" in url and "owner=user" in url


@pytest.mark.django_db(transaction=True)
def test_call_proxies_to_mcp_client() -> None:
    with schema_context("test_tenant"):
        Integration.objects.filter(provider="notion").delete()
        integ = Integration.objects.create(provider="notion", is_active=True)
        cred = Credential(integration=integ)
        cred.set_tokens({"access_token": "AT"})
        cred.save()
        result = ToolResult(is_error=False, text_blocks=['{"results": [{"id": "p1"}]}'])
        with patch(
            "apps.connectors.notion.integration.notion_client.call_tool",
            return_value=result,
        ) as called:
            r = NotionIntegration().call(integ, "search", {"query": "x"})
        called.assert_called_once_with("AT", "search", {"query": "x"})
        assert r.ok and r.data == {"results": [{"id": "p1"}]}

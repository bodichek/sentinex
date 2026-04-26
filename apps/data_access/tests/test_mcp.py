"""MCP Gateway + Google Workspace integration tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django_tenants.utils import schema_context

from apps.data_access.mcp.base import MCPCallResult
from apps.data_access.mcp.gateway import MCPGateway, RateLimitExceeded
from apps.data_access.mcp.integrations.google_workspace import GoogleWorkspaceIntegration
from apps.data_access.models import Credential, DataSnapshot, Integration, MCPCall
from apps.data_access.sync.google_workspace import run_sync


@pytest.mark.django_db(transaction=True)
class TestTokenEncryption:
    def test_roundtrip(self) -> None:
        with schema_context("test_tenant"):
            Integration.objects.filter(provider="google_workspace").delete()
            integration = Integration.objects.create(provider="google_workspace")
            cred = Credential(integration=integration)
            cred.set_tokens({"access_token": "secret", "refresh_token": "r"})
            cred.save()

            fetched = Credential.objects.get(pk=cred.pk)
            assert fetched.get_tokens() == {"access_token": "secret", "refresh_token": "r"}
            assert b"secret" not in bytes(fetched.encrypted_tokens)


@pytest.mark.django_db
class TestAuthorizationUrl:
    def test_builds_google_url(self, settings) -> None:  # type: ignore[no-untyped-def]
        settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
        url = GoogleWorkspaceIntegration().authorization_url(
            state="xyz", redirect_uri="http://x/cb"
        )
        assert "accounts.google.com" in url
        assert "state=xyz" in url
        assert "client_id=client-id" in url


@pytest.mark.django_db(transaction=True)
class TestMCPGateway:
    def _integration(self) -> Integration:
        Integration.objects.filter(provider="google_workspace").delete()
        integration = Integration.objects.create(provider="google_workspace", is_active=True)
        cred = Credential(integration=integration)
        cred.set_tokens({"access_token": "t", "refresh_token": "r"})
        cred.save()
        return integration

    def test_call_records_audit(self) -> None:
        with schema_context("test_tenant"):
            integration = self._integration()
            impl = GoogleWorkspaceIntegration()
            with patch.object(impl, "call", return_value=MCPCallResult(ok=True, data={"x": 1})):
                gateway = MCPGateway({"google_workspace": impl})
                result = gateway.call(integration, "gmail.messages.list", {"days": 7})
            assert result.ok is True
            assert MCPCall.objects.filter(integration=integration, tool="gmail.messages.list").count() == 1

    def test_rate_limit(self) -> None:
        with schema_context("test_tenant"):
            integration = self._integration()
            impl = GoogleWorkspaceIntegration()
            with patch.object(impl, "call", return_value=MCPCallResult(ok=True, data={})):
                gateway = MCPGateway({"google_workspace": impl})
                for _ in range(60):
                    gateway.call(integration, "tool", {})
                with pytest.raises(RateLimitExceeded):
                    gateway.call(integration, "tool", {})


@pytest.mark.django_db(transaction=True)
class TestSyncPipeline:
    def test_creates_snapshot(self) -> None:
        with schema_context("test_tenant"):
            Integration.objects.filter(provider="google_workspace").delete()
            integration = Integration.objects.create(provider="google_workspace", is_active=True)
            cred = Credential(integration=integration)
            cred.set_tokens({"access_token": "t", "refresh_token": "r"})
            cred.save()

            impl = GoogleWorkspaceIntegration()
            with patch.object(impl, "call", return_value=MCPCallResult(ok=True, data={"count": 3})):
                gateway = MCPGateway({"google_workspace": impl})
                snapshot = run_sync(gateway=gateway, days=7)
            assert snapshot is not None
            assert DataSnapshot.objects.count() >= 1
            assert snapshot.metrics["email"]["ok"] is True

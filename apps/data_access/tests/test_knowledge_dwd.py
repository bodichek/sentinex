"""Tests for the Domain-Wide Delegation auth helper (no real Google calls)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.data_access.mcp.integrations.google_workspace_dwd import (
    GoogleWorkspaceDWDIntegration,
    _load_sa_info,
    reset_sa_cache,
)

FAKE_SA = {
    "type": "service_account",
    "project_id": "test",
    "private_key_id": "abc",
    "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
    "client_email": "sa@test.iam.gserviceaccount.com",
    "client_id": "123",
}


@override_settings(GOOGLE_WORKSPACE_SA_JSON=json.dumps(FAKE_SA))
def test_load_sa_info_from_inline_env() -> None:
    reset_sa_cache()
    info = _load_sa_info()
    assert info["client_email"] == "sa@test.iam.gserviceaccount.com"


@override_settings(GOOGLE_WORKSPACE_SA_JSON="", GOOGLE_WORKSPACE_SA_JSON_PATH="")
def test_load_sa_info_unconfigured_raises() -> None:
    reset_sa_cache()
    with pytest.raises(RuntimeError):
        _load_sa_info()


def test_dwd_integration_authorization_url_raises() -> None:
    impl = GoogleWorkspaceDWDIntegration()
    with pytest.raises(NotImplementedError):
        impl.authorization_url("state", "https://example.com/cb")


def test_dwd_integration_unknown_tool_returns_error() -> None:
    impl = GoogleWorkspaceDWDIntegration()
    # Bypass the gateway — call the adapter directly with a fake Integration.
    with patch("apps.data_access.mcp.integrations.google_workspace_dwd._TOOL_REGISTRY", {}):
        result = impl.call(integration=None, tool="nope", params={})  # type: ignore[arg-type]
    assert result.ok is False
    assert "unknown tool" in result.error

"""Canva OAuth + integration unit tests (no real network)."""

from __future__ import annotations

import base64
import hashlib
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.connectors.canva import oauth
from apps.connectors.canva.client import ToolResult


def test_pkce_pair_uses_s256() -> None:
    verifier, challenge = oauth.generate_pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    assert challenge == expected


@override_settings(CANVA_CLIENT_ID="cid", CANVA_CLIENT_SECRET="csec")
def test_authorization_url_contains_pkce_and_state() -> None:
    url = oauth.authorization_url("STATE", "https://app/cb", "CHALLENGE")
    assert "client_id=cid" in url
    assert "state=STATE" in url
    assert "code_challenge=CHALLENGE" in url
    assert "code_challenge_method=S256" in url
    for scope_fragment in ("design%3Ameta%3Aread", "asset%3Aread"):
        assert scope_fragment in url


@override_settings(CANVA_CLIENT_ID="cid", CANVA_CLIENT_SECRET="csec")
def test_exchange_code_posts_pkce_verifier() -> None:
    fake = MagicMock()
    fake.json.return_value = {
        "access_token": "AT",
        "refresh_token": "RT",
        "expires_in": 3600,
        "scope": "design:meta:read",
        "token_type": "Bearer",
    }
    fake.raise_for_status.return_value = None
    with patch("apps.connectors.canva.oauth.httpx.post", return_value=fake) as posted:
        tokens = oauth.exchange_code("CODE", "https://app/cb", "VERIFIER")
    body = posted.call_args.kwargs["data"]
    assert body["code"] == "CODE"
    assert body["code_verifier"] == "VERIFIER"
    assert body["grant_type"] == "authorization_code"
    assert tokens["access_token"] == "AT"


def test_tool_result_first_json_parses_text_blocks() -> None:
    result = ToolResult(
        is_error=False,
        text_blocks=['{"id": "abc", "title": "Q1 plan"}', "trailing chatter"],
    )
    assert result.first_json() == {"id": "abc", "title": "Q1 plan"}


def test_tool_result_first_json_returns_none_when_no_json() -> None:
    assert ToolResult(is_error=False, text_blocks=["hi", "there"]).first_json() is None


@override_settings(CANVA_CLIENT_ID="cid", CANVA_CLIENT_SECRET="csec")
def test_refresh_tokens_keeps_old_refresh_when_server_omits_it() -> None:
    fake = MagicMock()
    fake.json.return_value = {
        "access_token": "AT2",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    fake.raise_for_status.return_value = None
    with patch("apps.connectors.canva.oauth.httpx.post", return_value=fake):
        new = oauth.refresh_tokens({"refresh_token": "RT_OLD", "scope": "design:meta:read"})
    assert new["refresh_token"] == "RT_OLD"
    assert new["access_token"] == "AT2"

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.connectors.microsoft365 import oauth
from apps.connectors.microsoft365.integration import Microsoft365Integration
from apps.connectors.microsoft365.sync import _summarise_messages


def test_provider_advertised() -> None:
    assert Microsoft365Integration.provider == "microsoft365"


@override_settings(MS365_CLIENT_ID="cid", MS365_CLIENT_SECRET="csec")
def test_authorization_url_contains_scopes_and_state() -> None:
    url = oauth.authorization_url("STATE", "https://app/cb")
    assert "client_id=cid" in url and "state=STATE" in url
    assert "Mail.Read" in url and "Files.Read.All" in url


@override_settings(MS365_CLIENT_ID="cid", MS365_CLIENT_SECRET="csec")
def test_refresh_tokens_keeps_old_refresh_when_omitted() -> None:
    fake = MagicMock()
    fake.json.return_value = {"access_token": "AT2", "expires_in": 3600}
    fake.raise_for_status.return_value = None
    with patch("apps.connectors.microsoft365.oauth.httpx.post", return_value=fake):
        new = oauth.refresh_tokens({"refresh_token": "RT_OLD", "scope": "Mail.Read"})
    assert new["refresh_token"] == "RT_OLD"
    assert new["access_token"] == "AT2"


def test_summarise_messages_counts_unread_and_senders() -> None:
    msgs = [
        {"from": {"emailAddress": {"address": "a@x.cz"}}, "isRead": False},
        {"from": {"emailAddress": {"address": "a@x.cz"}}, "isRead": True},
        {"from": {"emailAddress": {"address": "b@y.cz"}}, "isRead": False},
    ]
    s = _summarise_messages(msgs)
    assert s["total"] == 3
    assert s["unread"] == 2
    assert s["unique_senders"] == 2
    assert s["top_senders"][0][0] == "a@x.cz"

"""Microsoft Identity Platform OAuth 2.0 (v2.0 endpoint).

One connector, one OAuth handshake → access to Outlook, Teams chat,
Calendar, OneDrive via Microsoft Graph (https://graph.microsoft.com/v1.0).
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

DEFAULT_SCOPES = (
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Calendars.Read",
    "Files.Read.All",
    "ChannelMessage.Read.All",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
)


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "MS365_CLIENT_ID", "")
    sec = getattr(settings, "MS365_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("MS365_CLIENT_ID / MS365_CLIENT_SECRET not set")
    return cid, sec


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(DEFAULT_SCOPES),
        "state": state,
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": cid,
            "client_secret": sec,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": " ".join(DEFAULT_SCOPES),
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "scope": payload.get("scope"),
        "token_type": payload.get("token_type", "Bearer"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("MS365 credential missing refresh_token")
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": cid,
            "client_secret": sec,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
            "scope": " ".join(DEFAULT_SCOPES),
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", refresh),
        "expires_in": payload.get("expires_in"),
        "scope": payload.get("scope", tokens.get("scope")),
        "token_type": payload.get("token_type", "Bearer"),
    }

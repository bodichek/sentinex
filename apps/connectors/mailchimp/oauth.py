"""Mailchimp OAuth 2.0.

After token exchange we hit ``/oauth2/metadata`` to discover the data
center prefix (``us1``, ``us20`` ...) which determines the API base URL.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://login.mailchimp.com/oauth2/authorize"
TOKEN_URL = "https://login.mailchimp.com/oauth2/token"
METADATA_URL = "https://login.mailchimp.com/oauth2/metadata"


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "MAILCHIMP_CLIENT_ID", "")
    sec = getattr(settings, "MAILCHIMP_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("MAILCHIMP_CLIENT_ID / MAILCHIMP_CLIENT_SECRET not set")
    return cid, sec


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _fetch_metadata(access_token: str) -> dict[str, Any]:
    resp = httpx.get(
        METADATA_URL, headers={"Authorization": f"OAuth {access_token}"}, timeout=15
    )
    resp.raise_for_status()
    return dict(resp.json() or {})


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": cid,
            "client_secret": sec,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    access_token = payload["access_token"]
    meta = _fetch_metadata(access_token)
    return {
        "access_token": access_token,
        "dc": meta.get("dc"),
        "api_endpoint": meta.get("api_endpoint"),
        "login_url": meta.get("login_url"),
        "scope": payload.get("scope"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    # Mailchimp access tokens do not expire; nothing to refresh.
    return tokens

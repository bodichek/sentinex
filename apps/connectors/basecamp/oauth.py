"""Basecamp 4 OAuth via 37signals Launchpad.

After token exchange we GET ``authorization.json`` to discover which
account(s) the token grants access to and store the chosen ``account_id``
in the credential. All API calls then go to
``https://3.basecampapi.com/{account_id}/``.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://launchpad.37signals.com/authorization/new"
TOKEN_URL = "https://launchpad.37signals.com/authorization/token"
AUTH_INFO_URL = "https://launchpad.37signals.com/authorization.json"


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "BASECAMP_CLIENT_ID", "")
    sec = getattr(settings, "BASECAMP_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("BASECAMP_CLIENT_ID / BASECAMP_CLIENT_SECRET not set")
    return cid, sec


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "type": "web_server",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        params={
            "type": "web_server",
            "client_id": cid,
            "client_secret": sec,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    tokens = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
    }
    info = httpx.get(
        AUTH_INFO_URL,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        timeout=15,
    )
    info.raise_for_status()
    accounts = ((info.json() or {}).get("accounts")) or []
    bc4 = [a for a in accounts if a.get("product") == "bc3"] or accounts
    if not bc4:
        raise RuntimeError("Basecamp account list empty after install")
    chosen = bc4[0]
    tokens["account_id"] = chosen.get("id")
    tokens["account_href"] = chosen.get("href")
    tokens["account_name"] = chosen.get("name")
    return tokens


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Basecamp credential missing refresh_token")
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        params={
            "type": "refresh",
            "client_id": cid,
            "client_secret": sec,
            "refresh_token": refresh,
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", refresh),
        "expires_in": payload.get("expires_in"),
    }

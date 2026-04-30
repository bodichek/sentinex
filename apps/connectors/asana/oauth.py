"""Asana OAuth 2.0."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://app.asana.com/-/oauth_authorize"
TOKEN_URL = "https://app.asana.com/-/oauth_token"


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "ASANA_CLIENT_ID", "")
    sec = getattr(settings, "ASANA_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("ASANA_CLIENT_ID / ASANA_CLIENT_SECRET not set")
    return cid, sec


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "default",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


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
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "data": payload.get("data"),  # holds workspace + user info
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Asana credential missing refresh_token")
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
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

"""Calendly OAuth 2.0 (PKCE optional, we use confidential-client basic flow)."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://auth.calendly.com/oauth/authorize"
TOKEN_URL = "https://auth.calendly.com/oauth/token"


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "CALENDLY_CLIENT_ID", "")
    sec = getattr(settings, "CALENDLY_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("CALENDLY_CLIENT_ID / CALENDLY_CLIENT_SECRET not set")
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


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        auth=(cid, sec),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "owner": payload.get("owner"),  # URI of the user
        "organization": payload.get("organization"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Calendly credential missing refresh_token")
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        auth=(cid, sec),
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", refresh),
        "expires_in": payload.get("expires_in"),
        "owner": payload.get("owner", tokens.get("owner")),
        "organization": payload.get("organization", tokens.get("organization")),
    }

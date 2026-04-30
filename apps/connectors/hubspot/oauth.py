"""HubSpot OAuth 2.0."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"

DEFAULT_SCOPES = (
    "crm.objects.contacts.read",
    "crm.objects.companies.read",
    "crm.objects.deals.read",
    "crm.objects.owners.read",
    "tickets",
    "oauth",
)


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "HUBSPOT_CLIENT_ID", "")
    sec = getattr(settings, "HUBSPOT_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET not set")
    return cid, sec


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": " ".join(DEFAULT_SCOPES),
        "state": state,
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
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("HubSpot credential missing refresh_token")
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": cid,
            "client_secret": sec,
            "refresh_token": refresh,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", refresh),
        "expires_in": payload.get("expires_in"),
    }

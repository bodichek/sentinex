"""Atlassian Jira OAuth 2.0 (3LO).

After token exchange we list ``accessible-resources`` to discover the
``cloudId`` for the customer's Jira site and store it in the credential.
All API calls then use ``https://api.atlassian.com/ex/jira/{cloudId}``.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

DEFAULT_SCOPES = (
    "read:jira-work",
    "read:jira-user",
    "offline_access",
)


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "ATLASSIAN_CLIENT_ID", "")
    sec = getattr(settings, "ATLASSIAN_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("ATLASSIAN_CLIENT_ID / ATLASSIAN_CLIENT_SECRET not set")
    return cid, sec


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "audience": "api.atlassian.com",
        "client_id": cid,
        "scope": " ".join(DEFAULT_SCOPES),
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "client_id": cid,
            "client_secret": sec,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    access_token = payload["access_token"]

    res = httpx.get(
        RESOURCES_URL,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=15,
    )
    res.raise_for_status()
    resources = list(res.json() or [])
    if not resources:
        raise RuntimeError("Atlassian: no accessible resources for this token")
    primary = resources[0]
    return {
        "access_token": access_token,
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "cloud_id": primary.get("id"),
        "site_url": primary.get("url"),
        "site_name": primary.get("name"),
        "scopes": payload.get("scope"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Atlassian credential missing refresh_token")
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        json={
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

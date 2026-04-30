"""Salesforce OAuth 2.0 (web server flow)."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_HOST = "https://login.salesforce.com"  # use test.salesforce.com for sandboxes
AUTHORIZE_PATH = "/services/oauth2/authorize"
TOKEN_PATH = "/services/oauth2/token"
DEFAULT_SCOPES = ("api", "refresh_token", "offline_access")


def _client_creds() -> tuple[str, str, str]:
    cid = getattr(settings, "SALESFORCE_CLIENT_ID", "")
    sec = getattr(settings, "SALESFORCE_CLIENT_SECRET", "")
    host = getattr(settings, "SALESFORCE_LOGIN_HOST", AUTHORIZE_HOST)
    if not cid or not sec:
        raise RuntimeError("SALESFORCE_CLIENT_ID / SALESFORCE_CLIENT_SECRET not set")
    return cid, sec, host


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _, host = _client_creds()
    params = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": " ".join(DEFAULT_SCOPES),
        "state": state,
    }
    return f"{host}{AUTHORIZE_PATH}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, sec, host = _client_creds()
    resp = httpx.post(
        f"{host}{TOKEN_PATH}",
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
        "instance_url": payload["instance_url"],
        "id": payload.get("id"),
        "scope": payload.get("scope"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Salesforce credential missing refresh_token")
    cid, sec, host = _client_creds()
    resp = httpx.post(
        f"{host}{TOKEN_PATH}",
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
        "refresh_token": refresh,
        "instance_url": payload.get("instance_url", tokens.get("instance_url")),
        "scope": payload.get("scope", tokens.get("scope")),
    }

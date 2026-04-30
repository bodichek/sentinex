"""Dropbox OAuth 2.0 with PKCE.

The same access_token works for both the public Dropbox HTTP API
(``https://api.dropboxapi.com/2/...``) and the official Dropbox MCP
server (``https://mcp.dropbox.com/mcp``).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"

DEFAULT_SCOPES = (
    "account_info.read",
    "files.metadata.read",
    "files.content.read",
    "team_data.member",
)


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "DROPBOX_CLIENT_ID", "")
    sec = getattr(settings, "DROPBOX_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("DROPBOX_CLIENT_ID / DROPBOX_CLIENT_SECRET not set")
    return cid, sec


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verifier, challenge


def authorization_url(state: str, redirect_uri: str, code_challenge: str) -> str:
    cid, _ = _client_creds()
    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "token_access_type": "offline",
        "scope": " ".join(DEFAULT_SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
    cid, sec = _client_creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": cid,
            "client_secret": sec,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
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
        "account_id": payload.get("account_id"),
        "uid": payload.get("uid"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Dropbox credential missing refresh_token")
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
        "scope": payload.get("scope", tokens.get("scope")),
    }

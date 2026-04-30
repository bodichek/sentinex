"""Canva OAuth 2.1 with PKCE — install + refresh helpers.

Canva runs OAuth 2.1 (PKCE mandatory). The same access token works for
both the Canva Connect REST API and the official MCP server at
``https://mcp.canva.com/mcp``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import urllib.parse
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"

DEFAULT_SCOPES = (
    "design:meta:read",
    "design:content:read",
    "asset:read",
    "brandtemplate:meta:read",
    "folder:read",
    "profile:read",
    "comment:read",
)


def _basic_auth_header() -> dict[str, str]:
    client_id = getattr(settings, "CANVA_CLIENT_ID", "")
    client_secret = getattr(settings, "CANVA_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("CANVA_CLIENT_ID / CANVA_CLIENT_SECRET not set")
    raw = f"{client_id}:{client_secret}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def generate_pkce_pair() -> tuple[str, str]:
    """Return (verifier, S256 challenge) for the PKCE handshake."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def authorization_url(state: str, redirect_uri: str, code_challenge: str) -> str:
    client_id = getattr(settings, "CANVA_CLIENT_ID", "")
    if not client_id:
        raise RuntimeError("CANVA_CLIENT_ID not set")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(DEFAULT_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
    resp = httpx.post(
        TOKEN_URL,
        headers={**_basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
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
        "token_type": payload.get("token_type", "Bearer"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Canva credential missing refresh_token")
    resp = httpx.post(
        TOKEN_URL,
        headers={**_basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh},
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

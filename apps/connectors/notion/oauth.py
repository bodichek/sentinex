"""Notion OAuth 2.0.

The same access_token works for both the official Notion REST API
(``https://api.notion.com/v1``) and the official Notion MCP server
(``https://mcp.notion.com/mcp``). Tokens do not expire by default.
"""

from __future__ import annotations

import base64
import urllib.parse
from typing import Any

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"


def _client_creds() -> tuple[str, str]:
    cid = getattr(settings, "NOTION_CLIENT_ID", "")
    sec = getattr(settings, "NOTION_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("NOTION_CLIENT_ID / NOTION_CLIENT_SECRET not set")
    return cid, sec


def _basic_auth_header() -> dict[str, str]:
    cid, sec = _client_creds()
    raw = f"{cid}:{sec}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def authorization_url(state: str, redirect_uri: str) -> str:
    cid, _ = _client_creds()
    params = {
        "client_id": cid,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    resp = httpx.post(
        TOKEN_URL,
        headers={**_basic_auth_header(), "Content-Type": "application/json"},
        json={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "bot_id": payload.get("bot_id"),
        "workspace_id": payload.get("workspace_id"),
        "workspace_name": payload.get("workspace_name"),
        "owner": payload.get("owner"),
        "token_type": payload.get("token_type", "bearer"),
    }


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    # Notion access tokens do not expire under the public-integration model.
    return tokens

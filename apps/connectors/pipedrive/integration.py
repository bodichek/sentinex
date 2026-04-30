"""Pipedrive MCP integration — OAuth 2.0 (3-legged) with refresh-token flow."""

from __future__ import annotations

import base64
import logging
import urllib.parse
from typing import Any

import httpx
from django.conf import settings

from apps.connectors.pipedrive.client import OAUTH_TOKEN_URL, PipedriveClient
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "pipedrive"
AUTHORIZE_URL = "https://oauth.pipedrive.com/oauth/authorize"

DEFAULT_SCOPES = (
    "deals:read",
    "contacts:read",
    "users:read",
    "activities:read",
)


def _basic_auth_header() -> dict[str, str]:
    client_id = getattr(settings, "PIPEDRIVE_CLIENT_ID", "")
    client_secret = getattr(settings, "PIPEDRIVE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("PIPEDRIVE_CLIENT_ID / PIPEDRIVE_CLIENT_SECRET not set")
    raw = f"{client_id}:{client_secret}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    """Exchange a refresh_token for a fresh access_token."""
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Pipedrive credential missing refresh_token")
    resp = httpx.post(
        OAUTH_TOKEN_URL,
        headers=_basic_auth_header(),
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", refresh),
        "expires_in": payload.get("expires_in"),
        "api_domain": payload.get("api_domain", tokens.get("api_domain")),
        "scope": payload.get("scope", tokens.get("scope")),
    }


class PipedriveIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        client_id = getattr(settings, "PIPEDRIVE_CLIENT_ID", "")
        if not client_id:
            raise RuntimeError("PIPEDRIVE_CLIENT_ID not set")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(DEFAULT_SCOPES),
        }
        return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        resp = httpx.post(
            OAUTH_TOKEN_URL,
            headers=_basic_auth_header(),
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
            "api_domain": payload.get("api_domain"),
            "scope": payload.get("scope"),
        }

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return refresh_tokens(tokens)

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            with PipedriveClient(integration) as client:
                if tool == "pipelines.list":
                    return MCPCallResult(ok=True, data=client.list_pipelines())
                if tool == "stages.list":
                    return MCPCallResult(ok=True, data=client.list_stages())
                if tool == "users.list":
                    return MCPCallResult(ok=True, data=client.list_users())
                if tool == "deals.list":
                    return MCPCallResult(ok=True, data=client.iter_deals(**params))
                if tool == "persons.list":
                    return MCPCallResult(ok=True, data=client.iter_persons(**params))
                if tool == "activities.list":
                    return MCPCallResult(ok=True, data=client.iter_activities(**params))
                return MCPCallResult(ok=False, error=f"unknown tool: {tool}")
        except httpx.HTTPStatusError as exc:
            logger.warning("Pipedrive HTTP %s on %s", exc.response.status_code, tool)
            return MCPCallResult(ok=False, error=f"HTTP {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Pipedrive failure in %s", tool)
            return MCPCallResult(ok=False, error=str(exc))

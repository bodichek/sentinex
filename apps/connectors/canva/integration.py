"""Canva MCP integration — OAuth 2.1 + PKCE auth, MCP transport for tool calls."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.canva import client as canva_client
from apps.connectors.canva import oauth
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)

PROVIDER = "canva"


def _credential(integration: Integration) -> Credential:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Canva integration has no credential")
    return cred


def _refresh_and_persist(credential: Credential, tokens: dict[str, Any]) -> dict[str, Any]:
    new_tokens = oauth.refresh_tokens(tokens)
    merged = {**tokens, **new_tokens}
    credential.set_tokens(merged)
    credential.save()
    return merged


class CanvaIntegration(MCPIntegration):
    """OAuth + MCP-tool dispatcher.

    The ``call`` method forwards ``tool`` directly to Canva's MCP server,
    so any tool advertised by the upstream server (e.g. ``designs/list``,
    ``designs/export``, ``brand-templates/list``) is callable without
    code changes here. The list of tools is discovered at install time
    and cached in ``Integration.meta['tools']``.
    """

    provider = PROVIDER

    # OAuth flow needs a per-call PKCE verifier — the view layer handles
    # generation/storage and passes the verifier through to ``exchange_code``.
    def authorization_url(self, state: str, redirect_uri: str) -> str:
        # Compatibility shim: callers that still use the bare 2-arg signature
        # get a hard error; the view should use ``oauth.authorization_url``
        # directly to feed in a PKCE challenge.
        raise NotImplementedError(
            "Canva uses PKCE — call apps.connectors.canva.oauth.authorization_url(...) "
            "with a code_challenge generated via oauth.generate_pkce_pair()."
        )

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Canva PKCE: call apps.connectors.canva.oauth.exchange_code(code, "
            "redirect_uri, code_verifier) directly from the callback view."
        )

    def refresh_tokens(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return oauth.refresh_tokens(tokens)

    def call(
        self, integration: Integration, tool: str, params: dict[str, Any]
    ) -> MCPCallResult:
        try:
            credential = _credential(integration)
            tokens = credential.get_tokens()
            access_token = tokens.get("access_token", "")
            if not access_token:
                return MCPCallResult(ok=False, error="missing access_token")
            try:
                result = canva_client.call_tool(access_token, tool, params)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    tokens = _refresh_and_persist(credential, tokens)
                    result = canva_client.call_tool(tokens["access_token"], tool, params)
                else:
                    raise
            if result.is_error:
                return MCPCallResult(
                    ok=False,
                    error="; ".join(result.text_blocks) or "tool returned isError",
                )
            payload = result.first_json()
            return MCPCallResult(
                ok=True,
                data=payload if payload is not None else {"text": result.text_blocks},
            )
        except Exception as exc:
            logger.exception("Canva tool %s failed", tool)
            return MCPCallResult(ok=False, error=str(exc))

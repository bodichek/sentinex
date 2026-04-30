from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.connectors.dropbox import client as dropbox_client
from apps.connectors.dropbox import oauth
from apps.data_access.mcp.base import MCPCallResult, MCPIntegration
from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
PROVIDER = "dropbox"


def _credential(integration: Integration) -> Credential:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Dropbox integration has no credential")
    return cred


def _refresh_and_persist(credential: Credential, tokens: dict[str, Any]) -> dict[str, Any]:
    new_tokens = oauth.refresh_tokens(tokens)
    merged = {**tokens, **new_tokens}
    credential.set_tokens(merged)
    credential.save()
    return merged


class DropboxIntegration(MCPIntegration):
    provider = PROVIDER

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError(
            "Dropbox uses PKCE — call apps.connectors.dropbox.oauth.authorization_url(...) "
            "with a code_challenge from oauth.generate_pkce_pair()."
        )

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Dropbox PKCE: call apps.connectors.dropbox.oauth.exchange_code(code, "
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
                result = dropbox_client.call_tool(access_token, tool, params)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    tokens = _refresh_and_persist(credential, tokens)
                    result = dropbox_client.call_tool(tokens["access_token"], tool, params)
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
            logger.exception("Dropbox tool %s failed", tool)
            return MCPCallResult(ok=False, error=str(exc))

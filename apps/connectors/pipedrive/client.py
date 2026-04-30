"""Pipedrive REST API v1 client.

Pipedrive returns a per-account ``api_domain`` at OAuth time
(e.g. ``https://api-acme.pipedrive.com``) — we store it in the credential
and re-use it on every call. Token auto-refresh on 401.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import httpx
from django.utils import timezone

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)

OAUTH_TOKEN_URL = "https://oauth.pipedrive.com/oauth/token"
DEFAULT_TIMEOUT = 20.0


def _credential(integration: Integration) -> Credential:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Pipedrive integration has no credential")
    return cred


class PipedriveClient:
    """Thin httpx-based client. Handles 401 → refresh → retry once."""

    def __init__(
        self,
        integration: Integration,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._integration = integration
        self._credential = _credential(integration)
        tokens = self._credential.get_tokens()
        self._tokens = tokens
        api_domain = tokens.get("api_domain") or "https://api.pipedrive.com"
        self._client = http_client or httpx.Client(
            base_url=api_domain.rstrip("/"),
            timeout=DEFAULT_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PipedriveClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # -- token mgmt ---------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tokens.get('access_token','')}"}

    def _refresh(self) -> None:
        from apps.connectors.pipedrive.integration import refresh_tokens

        new_tokens = refresh_tokens(self._tokens)
        merged = {**self._tokens, **new_tokens}
        self._tokens = merged
        self._credential.set_tokens(merged)
        self._credential.save()

    # -- core call ----------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._client.get(f"/v1{path}", headers=self._auth_headers(), params=params)
        if resp.status_code == 401:
            self._refresh()
            resp = self._client.get(f"/v1{path}", headers=self._auth_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    # -- endpoints ----------------------------------------------------------

    def list_pipelines(self) -> list[dict[str, Any]]:
        return list((self._get("/pipelines") or {}).get("data") or [])

    def list_stages(self) -> list[dict[str, Any]]:
        return list((self._get("/stages") or {}).get("data") or [])

    def list_users(self) -> list[dict[str, Any]]:
        return list((self._get("/users") or {}).get("data") or [])

    def iter_deals(self, since: str | None = None, page_size: int = 100) -> list[dict[str, Any]]:
        """Page through /deals. ``since`` is ISO-8601 used with ``update_time``."""
        out: list[dict[str, Any]] = []
        start = 0
        while True:
            params: dict[str, Any] = {"start": start, "limit": page_size, "status": "all_not_deleted"}
            if since:
                params["filter_id"] = ""  # placeholder for future filter
            data = self._get("/deals", params)
            chunk = data.get("data") or []
            if since:
                chunk = [d for d in chunk if (d.get("update_time") or "") >= since]
            out.extend(chunk)
            pagination = (data.get("additional_data") or {}).get("pagination") or {}
            if not pagination.get("more_items_in_collection"):
                break
            start = int(pagination.get("next_start") or (start + page_size))
        return out

    def iter_persons(self, page_size: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        start = 0
        while True:
            data = self._get("/persons", {"start": start, "limit": page_size})
            chunk = data.get("data") or []
            out.extend(chunk)
            pagination = (data.get("additional_data") or {}).get("pagination") or {}
            if not pagination.get("more_items_in_collection"):
                break
            start = int(pagination.get("next_start") or (start + page_size))
        return out

    def iter_activities(
        self, days: int = 30, page_size: int = 100
    ) -> list[dict[str, Any]]:
        start_date = (timezone.now() - timedelta(days=days)).date().isoformat()
        out: list[dict[str, Any]] = []
        start = 0
        while True:
            data = self._get(
                "/activities",
                {"start": start, "limit": page_size, "start_date": start_date},
            )
            chunk = data.get("data") or []
            out.extend(chunk)
            pagination = (data.get("additional_data") or {}).get("pagination") or {}
            if not pagination.get("more_items_in_collection"):
                break
            start = int(pagination.get("next_start") or (start + page_size))
        return out

"""Ecomail API v2 client.

Auth: ``key`` header carrying the user's API key (Settings → API in Ecomail).
Docs: https://docs.ecomail.cz/  +  https://ecomailczv2.docs.apiary.io/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from apps.data_access.models import Credential, Integration

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20.0


def _api_key(integration: Integration) -> str:
    cred = Credential.objects.filter(integration=integration).first()
    if cred is None:
        raise ValueError("Ecomail integration has no credential")
    key = (cred.get_tokens() or {}).get("api_key")
    if not key:
        raise ValueError("Ecomail credential missing api_key")
    return str(key)


class EcomailClient:
    def __init__(
        self, integration: Integration, *, http_client: httpx.Client | None = None
    ) -> None:
        key = _api_key(integration)
        self._client = http_client or httpx.Client(
            base_url="https://api2.ecomail.cz",
            timeout=DEFAULT_TIMEOUT,
            headers={"key": key, "Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EcomailClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> Any:
        return self._get("/lists")

    def list_lists(self) -> list[dict[str, Any]]:
        data = self._get("/lists")
        return list(data) if isinstance(data, list) else list(data.get("data") or [])

    def list_campaigns(self) -> list[dict[str, Any]]:
        data = self._get("/campaigns")
        return list(data) if isinstance(data, list) else list(data.get("data") or [])

    def campaign_stats(self, campaign_id: int) -> dict[str, Any]:
        return dict(self._get(f"/campaigns/{campaign_id}/stats"))

    def list_subscribers(self, list_id: int, page: int = 1) -> Any:
        return self._get(f"/lists/{list_id}/subscribers", {"page": page})

    def list_automations(self) -> list[dict[str, Any]]:
        try:
            data = self._get("/pipelines")
            return list(data) if isinstance(data, list) else list(data.get("data") or [])
        except Exception:
            return []
